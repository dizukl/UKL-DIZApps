using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Net;
using System.Threading;
using System.Windows;

namespace DIZApp01 {
    internal class DIZApp01Impl:DIZApp01 {
        protected override void OutputDataReceived(object sender, DataReceivedEventArgs e) {
            Console.Out.WriteLine(sender.ToString() + ": " + e.Data);
        }
        protected override void ErrorDataReceived(object sender, DataReceivedEventArgs e) {
            Console.Out.WriteLine(sender.ToString() + " (Error): " + e.Data);
        }
        protected override void Write(string s) {
            Console.Out.Write(s);
        }
        protected override void WriteLine(string s) {
            Console.Out.WriteLine(s);
        }
        public DIZApp01Impl() {
            this.forceServerMode = false;
        }
    }

    internal class DIZApp01Main {
        [System.Runtime.InteropServices.DllImport("Kernel32")]
        private static extern bool SetConsoleCtrlHandler(SetConsoleCtrlEventHandler handler, bool add);
        private delegate bool SetConsoleCtrlEventHandler(CtrlType sig);

        private enum CtrlType {
            CTRL_C_EVENT = 0,
            CTRL_BREAK_EVENT = 1,
            CTRL_CLOSE_EVENT = 2,
            CTRL_LOGOFF_EVENT = 5,
            CTRL_SHUTDOWN_EVENT = 6
        }

        private static bool Handler(CtrlType signal) {
            switch (signal) {
                case CtrlType.CTRL_BREAK_EVENT:
                case CtrlType.CTRL_C_EVENT:
                case CtrlType.CTRL_LOGOFF_EVENT:
                case CtrlType.CTRL_SHUTDOWN_EVENT:
                case CtrlType.CTRL_CLOSE_EVENT:
                    dizapp.stop();

                    Environment.Exit(0);
                    return false;

                default:
                    return false;
            }
        }
        private static void CurrentDomain_ProcessExit(object sender, EventArgs e) {
            dizapp.stop();
        }

        private static DIZApp01Impl dizapp;

        static void Main(string[] args) {
            SetConsoleCtrlHandler(Handler, true);
            var exitEvent = new ManualResetEvent(false);
            Console.CancelKeyPress += (sender, eventArgs) => {
                eventArgs.Cancel = true;
                exitEvent.Set();
            };

            dizapp = new DIZApp01Impl();
            dizapp.run();
            exitEvent.WaitOne();

            dizapp.stop();
        }
    }
}
