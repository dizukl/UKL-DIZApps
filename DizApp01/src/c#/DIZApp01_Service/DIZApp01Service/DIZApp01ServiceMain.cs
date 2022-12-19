using System;
using System.Collections.Generic;
using System.Linq;
using System.ServiceProcess;
using System.Text;
using System.Threading.Tasks;
using System.IO;

namespace DIZApp01
{
    internal static class DIZApp01ServiceMain
    {
        /// <summary>
        /// Der Haupteinstiegspunkt für die Service-Anwendung.
        /// </summary>
        static void Main() {
            ServiceBase[] ServicesToRun = new ServiceBase[] {
                new DIZApp01Service()
            };
            ServiceBase.Run(ServicesToRun);
        }
    }
}
