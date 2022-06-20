using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Management;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace DIZApp01
{
    internal class Program
    {
        static Process p1 = null;
        static Process p2 = null;

        [System.Runtime.InteropServices.DllImport("Kernel32")]
        private static extern bool SetConsoleCtrlHandler(SetConsoleCtrlEventHandler handler, bool add);
        private delegate bool SetConsoleCtrlEventHandler(CtrlType sig);

        private enum CtrlType
        {
            CTRL_C_EVENT = 0,
            CTRL_BREAK_EVENT = 1,
            CTRL_CLOSE_EVENT = 2,
            CTRL_LOGOFF_EVENT = 5,
            CTRL_SHUTDOWN_EVENT = 6
        }

        static void Main(string[] args)
        {
            SetConsoleCtrlHandler(Handler, true);
            var exitEvent = new ManualResetEvent(false);
            Console.CancelKeyPress += (sender, eventArgs) => {
                eventArgs.Cancel = true;
                exitEvent.Set();
            };

            string strExeFilePath = System.Reflection.Assembly.GetExecutingAssembly().Location;
            string strWorkPath = System.IO.Path.GetDirectoryName(strExeFilePath);
            p1 = new Process();
            p1.StartInfo.FileName = strWorkPath + "\\..\\python\\python.exe";
            p1.StartInfo.Arguments = strWorkPath + "\\src\\scripts\\dizapp.py";
            p1.StartInfo.WorkingDirectory = strWorkPath;
            p1.StartInfo.UseShellExecute = false;
            p1.StartInfo.CreateNoWindow = true;
            p1.StartInfo.RedirectStandardOutput = true;
            p1.StartInfo.RedirectStandardError = true;
            p1.StartInfo.RedirectStandardInput = true;
            p1.OutputDataReceived += OutputDataReceived;
            p1.ErrorDataReceived += ErrorDataReceived;
            p1.Start();
            p2 = new Process();
            p2.StartInfo.FileName = strWorkPath + "\\..\\nginx\\nginx.exe";
            p2.StartInfo.WorkingDirectory = strWorkPath + "\\..\\nginx";
            p2.StartInfo.UseShellExecute = false;
            p2.StartInfo.CreateNoWindow = true;
            p2.StartInfo.RedirectStandardOutput = true;
            p2.StartInfo.RedirectStandardError = true;
            p2.StartInfo.RedirectStandardInput = true;
            p2.OutputDataReceived += OutputDataReceived;
            p2.ErrorDataReceived += ErrorDataReceived;
            p2.Start();

            exitEvent.WaitOne();

            KillProcessAndChildren(p1.Id);
            KillProcessAndChildren(p2.Id);
        }
        static void OutputDataReceived(object sender, DataReceivedEventArgs e)
        {
            Console.Out.WriteLine(sender.ToString() + ": " + e.ToString());
        }

        static void ErrorDataReceived(object sender, DataReceivedEventArgs e)
        {
            Console.Out.WriteLine(sender.ToString() + " (Error): " + e.ToString());
        }
        private static void KillProcessAndChildren(int pid)
        {
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

        private static bool Handler(CtrlType signal)
        {
            switch (signal)
            {
                case CtrlType.CTRL_BREAK_EVENT:
                case CtrlType.CTRL_C_EVENT:
                case CtrlType.CTRL_LOGOFF_EVENT:
                case CtrlType.CTRL_SHUTDOWN_EVENT:
                case CtrlType.CTRL_CLOSE_EVENT:
                    KillProcessAndChildren(p1.Id);
                    KillProcessAndChildren(p2.Id);
                    Environment.Exit(0);
                    return false;

                default:
                    return false;
            }
        }
    }
}
