param(
    [Parameter(Mandatory = $true)]
    [string] $InstallRoot,

    [switch] $AllowForeground,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $WechatIdeArgs
)

$ErrorActionPreference = "Stop"

$command = Join-Path $installRoot "wechatide.cmd"
if (-not (Test-Path -LiteralPath $command -PathType Leaf)) {
    throw "wechatide.cmd was not found at $command"
}

$allowForegroundRequested = $AllowForeground.IsPresent -or
    $env:WECHATIDE_ALLOW_FOREGROUND -match "^(?i:1|true|yes)$"
$focusGuard = $null

if (-not $allowForegroundRequested) {
    # DevTools activates its Electron window during many otherwise unattended CLI calls.
    Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

namespace Praxys
{
    public sealed class WechatIdeForegroundGuard : IDisposable
    {
        private const int RestoreWindowCommand = 9;
        private readonly string installRoot;
        private readonly Timer timer;
        private IntPtr lastNonWechatWindow;
        private int callbackActive;
        private int disposed;

        public WechatIdeForegroundGuard(string installRoot)
        {
            this.installRoot = Path.GetFullPath(installRoot)
                .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
                + Path.DirectorySeparatorChar;

            IntPtr foreground = GetForegroundWindow();
            if (!IsWechatIdeWindow(foreground))
            {
                lastNonWechatWindow = foreground;
            }

            timer = new Timer(PreserveFocus, null, 0, 50);
        }

        public void Dispose()
        {
            if (Interlocked.Exchange(ref disposed, 1) != 0)
            {
                return;
            }

            timer.Dispose();
            RestoreForegroundWindow();
        }

        private void PreserveFocus(object state)
        {
            if (Volatile.Read(ref disposed) != 0 ||
                Interlocked.Exchange(ref callbackActive, 1) != 0)
            {
                return;
            }

            try
            {
                IntPtr foreground = GetForegroundWindow();
                if (foreground == IntPtr.Zero)
                {
                    return;
                }

                if (IsWechatIdeWindow(foreground))
                {
                    RestoreWindow(foreground);
                }
                else
                {
                    lastNonWechatWindow = foreground;
                }
            }
            finally
            {
                Volatile.Write(ref callbackActive, 0);
            }
        }

        private void RestoreForegroundWindow()
        {
            IntPtr foreground = GetForegroundWindow();
            if (foreground != IntPtr.Zero && IsWechatIdeWindow(foreground))
            {
                RestoreWindow(foreground);
            }
        }

        private void RestoreWindow(IntPtr foreground)
        {
            IntPtr target = lastNonWechatWindow;
            if (target == IntPtr.Zero || target == foreground || !IsWindow(target))
            {
                return;
            }

            ShowWindowAsync(target, RestoreWindowCommand);
            if (!SetForegroundWindow(target))
            {
                SwitchToThisWindow(target, true);
            }
        }

        private bool IsWechatIdeWindow(IntPtr window)
        {
            if (window == IntPtr.Zero)
            {
                return false;
            }

            uint processId;
            GetWindowThreadProcessId(window, out processId);
            if (processId == 0)
            {
                return false;
            }

            try
            {
                using (Process process = Process.GetProcessById(checked((int)processId)))
                {
                    ProcessModule module = process.MainModule;
                    string executablePath = module == null ? null : module.FileName;
                    return executablePath != null &&
                        executablePath.StartsWith(installRoot, StringComparison.OrdinalIgnoreCase);
                }
            }
            catch (ArgumentException)
            {
                return false;
            }
            catch (InvalidOperationException)
            {
                return false;
            }
            catch (NotSupportedException)
            {
                return false;
            }
            catch (Win32Exception)
            {
                return false;
            }
        }

        [DllImport("user32.dll")]
        private static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(
            IntPtr window,
            out uint processId
        );

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool IsWindow(IntPtr window);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetForegroundWindow(IntPtr window);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool ShowWindowAsync(IntPtr window, int command);

        [DllImport("user32.dll")]
        private static extern void SwitchToThisWindow(
            IntPtr window,
            [MarshalAs(UnmanagedType.Bool)] bool altTab
        );
    }
}
"@

    $focusGuard = New-Object `
        -TypeName Praxys.WechatIdeForegroundGuard `
        -ArgumentList $InstallRoot
}

$exitCode = 1
Push-Location $env:SystemRoot
try {
    & $command @WechatIdeArgs
    $exitCode = $LASTEXITCODE
}
finally {
    if ($null -ne $focusGuard) {
        $focusGuard.Dispose()
    }
    Pop-Location
}

exit $exitCode
