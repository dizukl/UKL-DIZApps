import sys
import os

framefile = open('D:\\IIS\\ukl001\\test02\\dizapp01.html', "r")
framecontent = framefile.read()
framefile.close()

sys.stdout = open('D:\\IIS\\ukl001\\test02\\dizapp01.cnt', "w")
exec(open('D:\src\\test02.py').read())
sys.stdout.close()
sys.stdout = sys.__stdout__

contentfile01 = open('D:\\IIS\\ukl001\\test02\\dizapp01.cnt', "r")
dizapp01_content01 = contentfile01.read()
contentfile01.close()
os.remove(contentfile01.name)

ph01 = '<dizapp01_ph01 />'
framecontent = framecontent.replace(ph01, dizapp01_content01)


print('HTTP/1.x 200 OK')
print()
print(framecontent)
