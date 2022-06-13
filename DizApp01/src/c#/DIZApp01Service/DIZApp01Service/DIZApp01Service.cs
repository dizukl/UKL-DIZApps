using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Diagnostics;
using System.Linq;
using System.Management;
using System.ServiceProcess;
using System.Text;
using System.Threading.Tasks;

namespace DIZApp01Service
{
    public partial class DIZApp01Service : ServiceBase
    {
        EventLog el = null;
        Process p1 = null;
        Process p2 = null;

        public DIZApp01Service()
        {
            InitializeComponent();

            el = new System.Diagnostics.EventLog();
            if (!System.Diagnostics.EventLog.SourceExists("DIZApp01 Service"))
            {
                System.Diagnostics.EventLog.CreateEventSource(
                    "DIZApp01 Service", "Application");
            }
            el.Source = "DIZApp01 Service";
            el.Log = "Application";
        }

        protected override void OnStart(string[] args)
        {
            string strExeFilePath = System.Reflection.Assembly.GetExecutingAssembly().Location;
            string strWorkPath = System.IO.Path.GetDirectoryName(strExeFilePath);
            this.p1 = new Process();
            this.p1.StartInfo.FileName = strWorkPath + "\\..\\python\\python.exe";
            this.p1.StartInfo.Arguments = strWorkPath + "\\src\\scripts\\dizapp.py";
            this.p1.StartInfo.WorkingDirectory = strWorkPath;
            this.p1.StartInfo.UseShellExecute = false;
            this.p1.StartInfo.CreateNoWindow = true;
            this.p1.StartInfo.RedirectStandardOutput = true;
            this.p1.StartInfo.RedirectStandardError = true;
            this.p1.StartInfo.RedirectStandardInput = true;
            this.p1.OutputDataReceived += OutputDataReceived;
            this.p1.ErrorDataReceived += ErrorDataReceived;
            this.p1.Start();
            this.p2 = new Process();
            this.p2.StartInfo.FileName = strWorkPath + "\\..\\nginx\\nginx.exe";
            this.p2.StartInfo.WorkingDirectory = strWorkPath + "\\..\\nginx";
            this.p2.StartInfo.UseShellExecute = false;
            this.p2.StartInfo.CreateNoWindow = true;
            this.p2.StartInfo.RedirectStandardOutput = true;
            this.p2.StartInfo.RedirectStandardError = true;
            this.p2.StartInfo.RedirectStandardInput = true;
            this.p2.OutputDataReceived += OutputDataReceived;
            this.p2.ErrorDataReceived += ErrorDataReceived;
            this.p2.Start();

            //p.WaitForExit();
        }

        protected override void OnStop()
        {
            if (! this.p1.HasExited) 
            {
                KillProcessAndChildren(this.p1.Id);
            }
            if (! this.p2.HasExited)
            {
                KillProcessAndChildren(this.p2.Id);
                //this.p2.Kill();
            }
        }

        void OutputDataReceived(object sender, DataReceivedEventArgs e)
        {
            el.WriteEntry(sender.ToString() + ": " + e.ToString(), EventLogEntryType.Warning);
        }

        void ErrorDataReceived(object sender, DataReceivedEventArgs e)
        {
            el.WriteEntry(sender.ToString() + " (Error): " + e.ToString(), EventLogEntryType.Error);
        }

        private static void KillProcessAndChildren(int pid)
        {
            // Cannot close 'system idle process'.
            if (pid == 0)
            {
                return;
            }
            ManagementObjectSearcher searcher = new ManagementObjectSearcher
                    ("Select * From Win32_Process Where ParentProcessID=" + pid);
            ManagementObjectCollection moc = searcher.Get();
            foreach (ManagementObject mo in moc)
            {
                KillProcessAndChildren(Convert.ToInt32(mo["ProcessID"]));
            }
            try
            {
                Process proc = Process.GetProcessById(pid);
                proc.Kill();
            }
            catch (ArgumentException)
            {
                // Process already exited.
            }
        }
    }
}
