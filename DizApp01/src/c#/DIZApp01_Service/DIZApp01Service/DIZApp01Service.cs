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

namespace DIZApp01 {
    internal class DIZApp01ServiceImpl : DIZApp01 {
        EventLog evLog;
        public EventLog El { get => evLog; set => evLog = value; }

        protected override void OutputDataReceived(object sender, DataReceivedEventArgs e) {
            El.WriteEntry(sender.ToString() + ": " + e.Data, EventLogEntryType.Information);
        }
        protected override void ErrorDataReceived(object sender, DataReceivedEventArgs e) {
            El.WriteEntry(sender.ToString() + ": " + e.Data, EventLogEntryType.Error);
        }
        protected override void Write(string s) {
            El.WriteEntry(s, EventLogEntryType.Information);
        }
        protected override void WriteLine(string s) {
            El.WriteEntry(s, EventLogEntryType.Information);
        }
        public DIZApp01ServiceImpl() {
            this.forceServerMode = true;
            El = new System.Diagnostics.EventLog();
            if (!System.Diagnostics.EventLog.SourceExists("DIZApp01 Service")) {
                System.Diagnostics.EventLog.CreateEventSource(
                    "DIZApp01 Service", "Application");
            }
            El.Source = "DIZApp01 Service";
            El.Log = "Application";
        }
    }

    public partial class DIZApp01Service : ServiceBase {
        DIZApp01ServiceImpl dizapp;

        public DIZApp01Service() {
            InitializeComponent();

            dizapp = new DIZApp01ServiceImpl();
        }

        protected override void OnStart(string[] args) {
            dizapp.run();
        }

        protected override void OnStop() {
            dizapp.stop();
        }
    }
}
