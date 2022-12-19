using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Net;

namespace DIZApp01 {
    public abstract class DIZApp01 {
        protected Boolean forceServerMode = false;

        Process p1 = new Process();
        Process p2 = new Process();

        public void run() {
            Process currentProcess = Process.GetCurrentProcess();
            foreach (Process p in Process.GetProcesses()) {
                if ((p.ProcessName.StartsWith(currentProcess.ProcessName)) && (!p.Id.Equals(currentProcess.Id))) {
                    this.WriteLine("CAUTION: A process named " + currentProcess.ProcessName + " is already running. Starting anyway...");
                }
            }

            this.WriteLine("Starting DIZApp01...");

            string strWorkPath = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
            string lastPathComp = Path.GetFileName(strWorkPath).ToLower();
            string processShortName = currentProcess.ProcessName.ToLower().Replace("service", "");
            if (! lastPathComp.Equals(processShortName)) {
                string strNewWorkPath = Path.Combine(strWorkPath, processShortName);
                if (Directory.Exists(strNewWorkPath)) {
                    Directory.SetCurrentDirectory(strNewWorkPath);
                    strWorkPath = strNewWorkPath;
                }
            }

            Dictionary<string, string> c = new Dictionary<string, string>();
            String configFilePath = Path.Combine(strWorkPath, "dizapp01.conf");
            if (System.IO.File.Exists(configFilePath)) {
                StreamReader sr = new StreamReader(@configFilePath);
                string line;
                while ((line = sr.ReadLine()) != null) {
                    line = line.Trim();
                    if ((line.StartsWith("#")) || (!line.Contains(":")))
                        continue;
                    string[] arr = line.Split(':');
                    c.Add(arr[0].Trim(), arr[1].Trim());
                }
                sr.Close();
            }


            IPEndPoint[] ipEndPointArray = System.Net.NetworkInformation.IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners();
            foreach (IPEndPoint ipep in ipEndPointArray) {
                if (ipep.Port == int.Parse(c["appSslServerPort"])) {
                    this.WriteLine("CAUTION: SSL port " + c["appSslServerPort"] + " for Nginx is already in use. Starting anyway...");
                    break;
                }
            }
            foreach (IPEndPoint ipep in ipEndPointArray) {
                if (ipep.Port == int.Parse(c["appServerPort"])) {
                    this.WriteLine("CAUTION: Internal server port " + c["appServerPort"] + " is already in use. Exiting...");
                    Environment.Exit(-1);
                }
            }

            try {
                this.WriteLine("  Preparing Python subprocess...");

                p1.StartInfo.FileName = Path.Combine(strWorkPath, "..\\python\\python.exe");
                p1.StartInfo.Arguments = "-u \"src\\scripts\\dizapp.py\"";
                p1.StartInfo.WorkingDirectory = strWorkPath;
                p1.StartInfo.UseShellExecute = false;
                p1.StartInfo.CreateNoWindow = true;
                p1.StartInfo.RedirectStandardOutput = true;
                p1.StartInfo.RedirectStandardError = true;
                p1.StartInfo.RedirectStandardInput = true;
                p1.OutputDataReceived += OutputDataReceived;
                p1.ErrorDataReceived += ErrorDataReceived;

                this.WriteLine("  Starting Python subprocess...");
                p1.Start();

                this.WriteLine("  Preparing Nginx subprocess...");

                p2.StartInfo.FileName = Path.Combine(strWorkPath, "..\\nginx\\nginx.exe");
                p2.StartInfo.WorkingDirectory = Path.Combine(strWorkPath, "..\\nginx");
                p2.StartInfo.UseShellExecute = false;
                p2.StartInfo.CreateNoWindow = true;
                p2.StartInfo.RedirectStandardOutput = true;
                p2.StartInfo.RedirectStandardError = true;
                p2.StartInfo.RedirectStandardInput = true;
                p2.OutputDataReceived += OutputDataReceived;
                p2.ErrorDataReceived += ErrorDataReceived;

                this.WriteLine("  Starting Nginx subprocess...");
                p2.Start();

                if ((! this.forceServerMode) && (c["appMode"].Equals("Workstation", StringComparison.OrdinalIgnoreCase))) {
                    this.WriteLine("  Workstation mode... Wait 2 seconds to give background processes a chance...");
                    System.Threading.Thread.Sleep(2000);
                    this.WriteLine("  Workstation mode... Call browser with app page address...\r\n    https://localhost:" + c["appSslServerPort"]);
                    using (System.Net.Sockets.TcpClient client = new System.Net.Sockets.TcpClient()) {
                        var result = client.BeginConnect("localhost", int.Parse(c["appSslServerPort"]), null, null);
                        var success = result.AsyncWaitHandle.WaitOne(10000);
                        client.EndConnect(result);
                        if (success) {
                            System.Diagnostics.Process.Start("https://localhost:" + c["appSslServerPort"]);
                        }
                        else {
                            this.WriteLine("  App not avaiable via SSL on port " + c["appSslServerPort"] + ". Waited 10 seconds.\r\n" + 
                                "  Falling back to non-SSL call...\r\n" +
                                "    http://localhost:" + c["appServerPort"]);
                            result = client.BeginConnect("localhost", int.Parse(c["appServerPort"]), null, null);
                            success = result.AsyncWaitHandle.WaitOne(30000);
                            client.EndConnect(result);
                            if (success) {
                                System.Diagnostics.Process.Start("http://localhost:" + c["appServerPort"]);
                            }
                            else {
                                this.WriteLine("  App also not avaiable on port " + c["appServerPort"] + ". Waited 10 seconds." +
                                    "  Please check the settings.");
                            }
                        }
                    }
                }
            }
            catch (Exception ex) {
                this.WriteLine(ex.Message);
                this.WriteLine(ex.StackTrace);
            }

            this.WriteLine("DIZApp01 running.\r\n");
        }

        public void stop() {
            this.WriteLine("Stopping subprocesses and application...");
            KillProcessAndChildren(p1.Id);
            KillProcessAndChildren(p2.Id);
        }

        private void KillProcessAndChildren(int pid) {
            if (pid == 0) {
                return;
            }

            ManagementObjectSearcher searcher = new ManagementObjectSearcher
                    ("Select * From Win32_Process Where ParentProcessID=" + pid);
            ManagementObjectCollection moc = searcher.Get();
            foreach (ManagementObject mo in moc) {
                KillProcessAndChildren(Convert.ToInt32(mo["ProcessID"]));
            }
            try {
                Process proc = Process.GetProcessById(pid);
                proc.Kill();
            } catch (ArgumentException) {
                // Process already exited.
            }
        }

        protected abstract void OutputDataReceived(object sender, DataReceivedEventArgs e);
        protected abstract void ErrorDataReceived(object sender, DataReceivedEventArgs e);
        protected abstract void Write(String s);
        protected abstract void WriteLine(String s);
        protected void WriteLine() {
            this.WriteLine("");
        }
    }
}
