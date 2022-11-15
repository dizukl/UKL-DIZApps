import sys
import os
import html
import requests
from base64 import b64encode
from flask import Flask, request, send_from_directory
import json
import pandas
import numpy
from json2html import *
from flatten_json import flatten
import re
import random
import tempfile
import time
import datetime
import traceback
import webbrowser
import threading
import subprocess
from waitress import serve
import gc


### Create this app as a Flask app ###
app = Flask(__name__)
### End of Create this app as a Flask app ###


### Helper functions ###

#### Prepare basic page content for every page of this app
def init_frame_content():
    framecontent = ''
    framefile = open(os.path.join('gui', 'dizapp01.html'), "r")
    framecontent += framefile.read()
    framefile.close()

    dizapp01_content = app.app_config['appServerPort']
    framecontent = framecontent.replace('<dizapp01_ph00 />', dizapp01_content)
    return framecontent


#### Save data to a temporary file, depending on the file type and the data obj given
#### Used for providing downloads of query results
def saveDataToFile(obj = None, fileName = '', fileType = 'csv', append = False):
    fileNameExt = 'csv' if fileType=='csv' else 'json' if fileType=='json' else 'html' if fileType=='html' else 'dat'
    if fileName == '':
        fileName = 'dizapp01_' + str(time.time_ns()) + '_' + str(random.randrange(10000, 100000, 10)) + '.' + fileNameExt
    fullPath = os.path.join(tempfile.gettempdir(), fileName)
    try:
        if isinstance(obj, pandas.DataFrame):
            if fileType == 'html':
                framecontent = ''
                framefile = open(os.path.join('gui', 'dizapp01_export01.html'), "r")
                framecontent += framefile.read()
                framefile.close()

                dizapp01_content = obj.to_html(justify='left', escape=False, border=1)
                framecontent = framecontent.replace('<dizapp01_ph01 />', dizapp01_content)


                file = open(fullPath, 'a' if append else 'w')
                file.write(framecontent)
                file.close()
            else:
                if (not append) and ('true'==app.app_config['csvExportApplyUtf8BomTag'].lower()):
                    file = open(fullPath, 'wb')
                    file.write(b'\xef\xbb\xbf')
                    file.close()
                obj.to_csv(fullPath, sep=';', encoding='utf-8', mode='a')
        else:
            file = open(fullPath, 'ab' if append else 'wb')
            if fileType=='json':
                obj = json.dumps(obj, sort_keys=False, indent=4)
            file.write(str(obj).encode('utf8'))
            file.close()
    except Exception as ex:
        print(str(type(ex)))
        print(str(ex))
        return ''
    return fileName


#### Clean temporary files
#### Used for cleaning the temporary download files created by saveDataToFile()
def cleanFiles(olderThanDays = 1):
    now = time.time()
    try:
        tempdir = tempfile.gettempdir()
        for file in os.listdir(tempdir):
            if file.startswith("dizapp01_") and (os.stat(os.path.join(tempdir, file)).st_mtime < (now - (olderThanDays * 86400))):
                os.remove(os.path.join(tempdir, file))
    except Exception as ex:
        print(str(type(ex)))
        print(str(ex))


#### Create an error page for the user
#### Used in some error conditions of the app
def getErrorPage(errStr = 'General error'):
    framecontent = init_frame_content()
    framecontent = framecontent.replace('<dizapp01_ph01 />', '<b>Error</b>')
    framecontent = framecontent.replace('<dizapp01_ph02 />', errStr)
    framecontent = framecontent.replace('<dizapp01_ph03 />', '')
    return framecontent

### End of Helper functions ###


### App path functions ###

##### App root path ###
@app.route('/')
def exec_start():
    framecontent = init_frame_content()
    dizapp01_content = open(os.path.join('gui', 'query01.html'), "r").read()
    
    htmlOptions = ''
    for key in app.fhirServers.keys():
        htmlOptions += '<option value="' + key + '" ' + ('selected' if key==app.app_config['defaultFhirServer'] else '') + \
                       '>' + app.fhirServers[key]['name'] + ' - ' + app.fhirServers[key]['url'] + '</option>'

    defaultFhirSearchString = app.app_config['defaultFhirSearchString']

    dizapp01_content = dizapp01_content.replace('<dizapp01_ph01 />', htmlOptions)
    dizapp01_content = dizapp01_content.replace('<dizapp01_ph02 />', defaultFhirSearchString)

    framecontent = framecontent.replace('<dizapp01_ph01 />', dizapp01_content)
    framecontent = framecontent.replace('<dizapp01_ph02 />', '')
    framecontent = framecontent.replace('<dizapp01_ph03 />', '')
    return framecontent


##### Query path ###
@app.route('/exec_fhir_query', methods=['GET', 'POST'])
def exec_fhir_query():
    if request.method != 'POST':
        error_content = 'Page requires POST method, not ' + request.method + '.'
        return getErrorPage(error_content)

    # keep start time for counting execution time
    startTime = datetime.datetime.now()

    # Make the form data given to this method easily available via p variable
    p = request.form
    c = app.app_config

    # Check some basic criteria    
    if ('newQuery' not in p) and ('nextPageLink' not in p) and ('prevPageLink' not in p) and ('firstPageLink' not in p) and ('lastPageLink' not in p):
        error_content = 'Not enough information to execute query'
        return getErrorPage(error_content)
    if ('newQuery' in p) and (p['searchParameters'].strip() == ''):
        error_content = 'Empty query'
        return getErrorPage(error_content)

    # init some helper variables
    page = '(not available)'
    if ('page' not in p) or ('firstPage' in p):
        page = 1
    elif 'lastPage' in p:
        page = '(not available)'
    elif p['page'].isnumeric():
        page = int(p['page']) + (1 if 'nextPage' in p else (-1 if 'prevPage' in p else 0))

    fhirServer_url = ''
    fhirServer_params = ''
    resourceType = ''
    requestData = ''
    contentType = ''
    newQuery = 'newQuery' in p

    fhirServer_url = \
                   p['prevPageLink'] if 'prevPage' in p else \
                   p['nextPageLink'] if 'nextPage' in p else \
                   p['firstPageLink'] if 'firstPage' in p else \
                   p['lastPageLink'] if 'lastPage' in p else ''

    # Parse query statement, build FHIR server url params and additional requestData
    # When executing a user query, the first request to the FHIR server uses POST method to pass the size limits of GET requests.
    # For this first request, the requestData variable holds the query statement to be transferred by POST 
    # Subsequent requests (next/previous/last/first page) are executet via GET method 
    isIdQuery = False
    if newQuery:
        # Basic request parsing
        fhirServer_url = c[p['fhirServer']+'_url'] + ':' + c[p['fhirServer']+'_port'] + c[p['fhirServer']+'_path']
        requestDataFull = p['searchParameters'].strip()
        if requestDataFull.startswith('/'):
            requestDataFull = requestDataFull[1:]
        isIdQuery = False
        if re.search('^[A-Za-z]+\?', requestDataFull):
            isIdQuery = False
            resourceType = requestDataFull.split('?', 1)[0]
            requestData = requestDataFull.split('?', 1)[1]
        elif re.search('^[A-Za-z]+\/', requestDataFull):
            isIdQuery = True
            resourceType = requestDataFull.split('/', 1)[0]
            requestData = requestDataFull.split('/', 1)[1]
        else:
            isIdQuery = False
            resourceType = requestDataFull
            requestData = ''
            
        # Some replacements ... used for convenience when users write the FHIR query
        resourceType = resourceType.replace("\r\n", "").replace("\n", "")
        requestData = requestData.replace("\r\n", "&").replace("\n", "&")

        # Add page size for FHIR server paging to the requestData
        pageSize = c['fhirServerFullExportPageSize'] if p['exportResultMode'] == 'expFull' else p['resultPageSize']
        reic = re.IGNORECASE
        re.IGNORECASE = True
        requestData += '' if  (isIdQuery or re.search('_id\s*=', requestData)) else (('' if requestData == ''  else '&') + '_count=' + str(pageSize))
        re.IGNORECASE = reic
        
        if isIdQuery:
            fhirServer_params = '/' + resourceType + '/' + requestData
        else:
            fhirServer_params = '/' + resourceType + '/_search'
        contentType = 'application/x-www-form-urlencoded'

    # Create FHIR server url 
    fhirServer_url_params = fhirServer_url + fhirServer_params
    # Create FHIR server authentication data
    fhirServer_user_pass = ''
    try:
        #if p['fhirServerLogin'] == '':
        if 'usePresetLogin' in p:
            fhirServer_user_pass = c[p['fhirServer']+'_user'] + ':' + c[p['fhirServer']+'_pw']
        else:
            fhirServer_user_pass = p['fhirServerLogin'] + ':' + p['fhirServerPw']
        fhirServer_user_pass = b64encode(fhirServer_user_pass.encode('ascii')).decode('ascii')
    except Exception as ex:
        pass
    authData = 'None' if fhirServer_user_pass == '' else 'Basic %s' % fhirServer_user_pass

    # Retrieve result from FHIR server in 3 steps:
    # 1. Execute FHIR server query
    # 2. Remove some result fields depending on the options omitMeta, omitText and omitIdentifierType
    # 3. Check if exportResultMode=='expFull'; if true, retrieve nextPageLink and repeat while loop
    r_raw = None       # raw result content of FHIR server query
    r_json_array = []  # array of all page contents in json format; can have more than one element if exportResultMode=='expFull'
    httpStatusInfoStr = ''
    queryProcessFinished = False
    try:
        while not queryProcessFinished:
            if (newQuery) and (not isIdQuery):
                requestHeaders = { 'Authorization' : authData, 'Accept' : 'application/fhir+json', 'content-type' : contentType }
                r_raw = requests.post(url=fhirServer_url_params, headers=requestHeaders, verify=('False'!=c[p['fhirServer']+'_verifySsl']), data=requestData, timeout=int(c[p['fhirServer']+'_timeout']))
            else:
                requestHeaders = { 'Authorization' : authData, 'Accept' : 'application/fhir+json' }
                r_raw = requests.get(url=fhirServer_url_params, headers=requestHeaders, verify=('False'!=c[p['fhirServer']+'_verifySsl']), timeout=int(c[p['fhirServer']+'_timeout']))
            r_json = json.loads(r_raw.text) # single result page content
            if (r_json['resourceType'] == 'Bundle') and ('entry' in r_json):
                for e in r_json['entry']:
                    r = e['resource']
                    if ('omitMeta' in p) and ('meta' in r):
                        del r['meta']
                    if ('omitText' in p) and ('text' in r):
                        del r['text']
                    if 'omitIdentifierType' in p:
                        if 'identifier' in r:
                            for i in r['identifier']:
                                if 'type' in i:
                                    del i['type']
            else:
                if ('omitMeta' in p) and ('meta' in r_json):
                    del r_json['meta']
                if ('omitText' in p) and ('text' in r_json):
                    del r_json['text']
                if 'omitIdentifierType' in p:
                    if 'identifier' in r_json:
                        for i in r_json['identifier']:
                            if 'type' in i:
                                del i['type']
            r_json_array.append(r_json)
            nextPageLink = ''
            try:
                nextPageLink = [ (i) for i in r_json['link'] if i['relation'] == 'next' ][0]['url']
                if 'true' == c[p['fhirServer']+'_applyFirelyPageLinkCorrection'].lower().strip():
                    nextPageLink = nextPageLink.replace('/_search?', '?')
            except Exception as ex:
                pass
            if (p['exportResultMode'] == 'expFull') and (r_json['resourceType'] == 'Bundle') and (nextPageLink != ''):
                newQuery = False
                fhirServer_url_params = nextPageLink
                queryProcessFinished = False
            else:
                queryProcessFinished = True
    except Exception as ex:
        error_content = '<div>Error:</div><br /><br />' + \
                        r_raw.text + '<br /><br />' + \
                        str(ex) + '<br /><br />' + \
                        '<div>... while retrieving the result.</div><br /><br />'
        return getErrorPage(error_content)
    if len(r_json_array) == 0:
        error_content = '<div>Error while retrieving the result:</div><br /><br />' + r_raw.text + '<br /><br />'
        return getErrorPage(error_content)

    httpStatusInfoStr = html.escape(str(r_raw))

    # Retrieve count (total) entry from result
    count = -1
    if r_json_array[0]['resourceType'] == 'Bundle':
        try:
            count = r_json_array[0]['total']
        except Exception:
            count = "(not explicitly returned)"
    else:
        count = "(Single item result)"

    # Parse page content for page link data
    prevPageLink = ''; nextPageLink = ''; firstPageLink = ''; lastPageLink = ''
    try:
        prevPageLink = [ (i) for i in r_json_array[0]['link'] if (i['relation'] == 'previous') or (i['relation'] == 'prev') ][0]['url']
    except Exception:
        pass
    try:
        nextPageLink = [ (i) for i in r_json_array[0]['link'] if i['relation'] == 'next' ][0]['url']
    except Exception:
        pass
    try:
        firstPageLink = [ (i) for i in r_json_array[0]['link'] if i['relation'] == 'first' ][0]['url']
    except Exception:
        pass
    try:
        lastPageLink = [ (i) for i in r_json_array[0]['link'] if i['relation'] == 'last' ][0]['url']
    except Exception:
        pass

    # Create output objects:
    # outputDataFrame for showing result in web page and
    # fileOutputObject for writing result to export file
    outputDataFrame = pandas.DataFrame()
    fileOutputObject = None
    if ('entry' not in r_json_array[0]) or (r_json_array[0]['resourceType'] != 'Bundle'):
        if p['outputMode'] == 'outputMode01':
            outputDataFrame = outputDataFrame.append(pandas.DataFrame({'Result': [r_json_array[0]]}))
        if p['outputMode'] == 'outputMode02':
            outputDataFrame = outputDataFrame.append(pandas.DataFrame({'Result': [r_json_array[0]]}))
        elif p['outputMode'] == 'outputMode03':
            outputDataFrame = outputDataFrame.append(pandas.DataFrame({'Result': [json2html.convert(r_json_array[0])]}))
        elif p['outputMode'] == 'outputMode04':
            outputDataFrame = outputDataFrame.append(pandas.json_normalize(r_json_array[0]))
        elif p['outputMode'] == 'outputMode05':
            outputDataFrame = outputDataFrame.append(pandas.json_normalize(flatten(r_json_array[0])))
        else:
            fileOutputObject = outputDataFrame
    else:
        # Here r_json_array[0]['resourceType'] == 'Bundle' is True
        try:
            while len(r_json_array) > 0:
                if p['outputMode'] == 'outputMode01':
                    outputDataFrame = outputDataFrame.append(pandas.DataFrame({'Result': [r_json_array[0]]}))
                elif p['outputMode'] == 'outputMode02':
                    outputDataFrame = outputDataFrame.append(pandas.DataFrame(r_json_array[0]['entry']))
                elif p['outputMode'] == 'outputMode03':
                    tmpDataFrame = pandas.DataFrame(r_json_array[0]['entry'])[['resource']]
                    tmpDataFrame['resource'] = tmpDataFrame.apply(lambda L: json2html.convert(L[0]), axis=1)
                    outputDataFrame = outputDataFrame.append(tmpDataFrame)
                elif p['outputMode'] == 'outputMode04':
                    outputDataFrame = outputDataFrame.append(pandas.json_normalize(r_json_array[0]['entry']))
                elif p['outputMode'] == 'outputMode05':
                    r_flat = [flatten(d) for d in r_json_array[0]['entry']]
                    outputDataFrame = outputDataFrame.append(pandas.json_normalize(r_flat))
                del r_json_array[0]
                gc.collect()
        except Exception as ex:
            outputDataFrame = pandas.DataFrame({'Error': 'Exception: ' + str(type(ex)) + "<br />" + str(ex) + "<br /><br />" + str(r_json_array[0])})
    if len(outputDataFrame.index) > 0:
        outputDataFrame.reset_index(drop=True, inplace=True)
        outputDataFrame.index += 1

    # Save output result to file (if gui option is set)
    downloadFileName = ''
    if (p['exportResultMode'] == 'expPage') or (p['exportResultMode'] == 'expFull'):
        if p['outputMode'] == 'outputMode01':
            if outputDataFrame.size > 0:
                downloadFileName = saveDataToFile(obj = outputDataFrame['Result'].iloc[0], fileName = '', fileType = 'json', append = False)
        elif p['outputMode'] == 'outputMode02':
            downloadFileName = saveDataToFile(obj = outputDataFrame, fileName = '', fileType = 'csv', append = False)
        elif p['outputMode'] == 'outputMode03':
            downloadFileName = saveDataToFile(obj = outputDataFrame, fileName = '', fileType = 'html', append = False)
        elif p['outputMode'] == 'outputMode04':
            downloadFileName = saveDataToFile(obj = outputDataFrame, fileName = '', fileType = 'csv', append = False)
        elif p['outputMode'] == 'outputMode05':
            downloadFileName = saveDataToFile(obj = outputDataFrame, fileName = '', fileType = 'csv', append = False)

    # count execution time
    endTime = datetime.datetime.now()
    timeDiff = endTime - startTime

    # Return download file directly
    #return getErrorPage(str(p))

    if ((p['exportResultMode'] != 'noExp') and ('resultDownloadDirectly' in p)):
        ## Housekeeping...
        del outputDataFrame
        gc.collect()
        return download(downloadFileName);

    # Build web output
    ## Build web output header of query result, including page data and page links
    queryStatement = p['queryStatement'] if 'queryStatement' in p else fhirServer_params + ('' if requestData == '' else '/' if isIdQuery else '?') + requestData

    dizapp02_content = '<div style="width:100%;">'
    dizapp02_content += '<table>'
    dizapp02_content += '<tr><td><b>Result</b></td><td><div style="width:50px;"></div></td><td>Count: ' + str(count) + '</td></tr>'
    dizapp02_content += '</table>'
    dizapp02_content += '<table>'
    if p['exportResultMode'] != 'expFull':
        dizapp02_content += '<tr><td>Page: ' + str(page)
        dizapp02_content += '&nbsp;&nbsp;&nbsp;Page Size: ' + str(p['resultPageSize']) + '</td>'
        dizapp02_content += '<td><div style="width:20px"></div></td>'
        if 'true' == c[p['fhirServer']+'_applyFirelyPageLinkCorrection'].lower().strip():
            nextPageLink = nextPageLink.replace('/_search?', '?')
            prevPageLink = prevPageLink.replace('/_search?', '?')
            lastPageLink = lastPageLink.replace('/_search?', '?')
            firstPageLink = firstPageLink.replace('/_search?', '?')
        dizapp02_content += '<td><form method="post" action="/exec_fhir_query">'
        dizapp02_content += '<input type="hidden" id="page" name="page" value="' + str(page) + '"></input>'
        dizapp02_content += '<input type="hidden" id="firstPageLink" name="firstPageLink" value="' + firstPageLink + '"></input>'
        dizapp02_content += '<input type="hidden" id="prevPageLink" name="prevPageLink" value="' + prevPageLink + '"></input>'
        dizapp02_content += '<input type="hidden" id="nextPageLink" name="nextPageLink" value="' + nextPageLink + '"></input>'
        dizapp02_content += '<input type="hidden" id="lastPageLink" name="lastPageLink" value="' + lastPageLink + '"></input>'
        dizapp02_content += '<input type="hidden" id="queryStatement" name="queryStatement" value="' + queryStatement + '"></input>'
        dizapp02_content += '<input type="hidden" id="fhirServer" name="fhirServer" value="' + p['fhirServer'] + '"></input>'
        dizapp02_content += '<input type="hidden" id="fhirServer" name="fhirServerLogin" value="' + p['fhirServerLogin'] + '"></input>'
        dizapp02_content += '<input type="hidden" id="fhirServer" name="fhirServerPw" value="' + p['fhirServerPw'] + '"></input>'
        dizapp02_content += '<input type="hidden" id="outputMode" name="outputMode" value="' + p['outputMode'] + '"></input>'
        dizapp02_content += '<input type="hidden" id="exportResultMode" name="exportResultMode" value="' + p['exportResultMode'] + '"></input>'
        if 'omitMeta' in p:
            dizapp02_content += '<input type="hidden" id="omitMeta" name="omitMeta" value="omitMeta"></input>'
        if 'omitText' in p:
            dizapp02_content += '<input type="hidden" id="omitText" name="omitText" value="omitText"></input>'
        if 'omitIdentifierType' in p:
            dizapp02_content += '<input type="hidden" id="omitIdentifierType" name="omitIdentifierType" value="omitIdentifierType"></input>'
        dizapp02_content += '<input type="hidden" id="resultPageSize" name="resultPageSize" value="' + p['resultPageSize'] + '"></input>'
        dizapp02_content += '<input type="submit" id="firstPage" name="firstPage" value="First Page" title="Using Link: ' + \
                            firstPageLink + '" ' + ('disabled' if firstPageLink == '' else '') + '></input>&nbsp;&nbsp;&nbsp;'
        dizapp02_content += '<input type="submit" id="prevPage" name="prevPage" value="Previous Page" title="Using Link: ' + \
                            prevPageLink + '" ' + ('disabled' if prevPageLink == '' else '') + '></input>&nbsp;'
        dizapp02_content += '<input type="submit" id="nextPage" name="nextPage" value="Next Page" title="Using Link: ' + \
                            nextPageLink + '" ' + ('disabled' if nextPageLink == '' else '') + '></input>&nbsp;&nbsp;&nbsp;'
        dizapp02_content += '<input type="submit" id="lastPage" name="lastPage" value="Last Page" title="Using Link: ' + \
                            lastPageLink + '" ' + ('disabled' if lastPageLink == '' else '') + '></input>'
        dizapp02_content += '</form></td>'
        dizapp02_content += '</tr>'
    dizapp02_content += "</table>"
    dizapp02_content += "<div>"

    ## Build whole web output (3 content parts)
    ### Part 1
    dizapp01_content = \
        '<div style="width:100%;"><table>' + \
        '<tr><td><b>FHIR Server:</b></td><td><div style="word-break:break-all">' + fhirServer_url + '</div></td></tr>' + \
        '<tr><td><b>Query statement:</b></td><td><div style="word-break:break-all">' + queryStatement + '</div></td></tr>' + \
        "<tr><td><b>HTTP Status:</b></td><td>" + httpStatusInfoStr + "</td></tr>" + \
        "</table></div>"

    ### Part 2
    escape = True if p['outputMode'] == 'outputMode01' else False
    fileDownloadLink = ''
    if downloadFileName == '':
        fileDownloadLink = '&lt;Link not available&gt;'
    else:
        fileDownloadLink = '<a href="/download/' + downloadFileName + '" download>' + downloadFileName + '</a>'
    if p['exportResultMode'] == 'expPage':
        dizapp02_content += '<div style="width: 100%;height: 8px;"></div>' + \
                            '<div style="width: 100%;">Page content saved to file ' + fileDownloadLink + '</div>' + \
                            '<div style="width: 100%;height: 8px;"></div>'
    if p['exportResultMode'] == 'expFull':
        dizapp02_content += '<div style="width: 100%;height: 8px;"></div>' + \
                            '<div style="width: 100%;">Page content saved to file ' + fileDownloadLink + '</div>' + \
                            '<div style="width: 100%;height: 8px;"></div>'
        if len(outputDataFrame.index) > 10:
            dizapp02_content += '<div style="width: 100%;">Please note: In Full-Export mode only maximal 10 rows are shown. ' + \
                                'For the complete result see the download file.</div>' + \
                                '<div style="width: 100%;height: 8px;"></div>'
    dizapp02_content += outputDataFrame.to_html(max_rows=(10 if p['exportResultMode'] == 'expFull' else None), justify='left', escape=escape, border=1, classes="table_resulttable")
    dizapp02_content += "</div>"

    ### Part 3
    dizapp03_content = 'Request executed in (time): ' + str(timeDiff)

    ## Fill web page template with web output
    framecontent = init_frame_content()
    framecontent = framecontent.replace('<dizapp01_ph01 />', dizapp01_content)
    framecontent = framecontent.replace('<dizapp01_ph02 />', dizapp02_content)
    framecontent = framecontent.replace('<dizapp01_ph03 />', dizapp03_content)

    # Housekeeping...
    del outputDataFrame
    gc.collect()

    return framecontent


##### Data download path ###
@app.route('/download/<path:filename>', methods=['GET', 'POST'])
def download(filename):
    file_name, file_ext = os.path.splitext(filename)
    mimetype = 'text/csv'
    if file_ext == 'csv':
        mimetype = 'text/csv'
    elif file_ext == 'json':
        mimetype = 'application/json'
    else:
        mimetype = 'text/plain'
    return send_from_directory(tempfile.gettempdir(), filename, mimetype=mimetype)


##### Example query path ###
@app.route('/examples_fhirsearch', methods=['GET', 'POST'])
def examples_fhirsearch():
    framecontent = init_frame_content()
    dizapp01_content01 = open(os.path.join('gui', 'fhirsearch_example_queries.txt'), "r").read()
    dizapp01_content01 = html.escape(dizapp01_content01, True)
    framecontent = framecontent.replace('<dizapp01_ph01 />', '<b>Example Queries (FHIR Search)</b>')
    framecontent = framecontent.replace('<dizapp01_ph02 />', '<pre>' + dizapp01_content01 + '</pre>')
    framecontent = framecontent.replace('<dizapp01_ph03 />', '')
    return framecontent


##### Favicon path ###

@app.route('/favicon.ico', methods=['GET', 'POST']) 
def favicon():
    return send_from_directory(os.path.join(app.root_path, "gui"), 'diz01.ico', mimetype='image/vnd.microsoft.icon')

### End of App path functions ###


### Main section ###

#### Threads started by main entry point ###

def runServer():
    serve(app, host='127.0.0.1', port=app.app_config['appServerPort'])

def runBrowser():
    webbrowser.open('http://localhost:' + app.app_config['appServerPort'])


#### Main entry point ###

if __name__ == '__main__':
    cleanFiles(1)

    app.fhirServers = {}
    app.app_config = {}
    with open('dizapp01.conf') as conffile:
        for line in conffile:
            if ':' in line:
                key, val = line.partition(':')[::2]
                app.app_config[key.strip()] = val.strip()
    with open(os.path.join('sec', 'dizapp01.secrets')) as conffile:
        for line in conffile:
            if ':' in line:
                key, val = line.partition(':')[::2]
                app.app_config[key.strip()] = val.strip()

    for key, val in app.app_config.items():
        if key.startswith('fhirServer'):
            if '_' in key:
                pref, suff = key.partition('_')[::2]
                if pref not in app.fhirServers:
                    app.fhirServers[pref] = {}
                app.fhirServers[pref][suff] = val 

    serverThread = threading.Thread(target=runServer)
    serverThread.start()

    print("Test")

### End of Main entry point ###
