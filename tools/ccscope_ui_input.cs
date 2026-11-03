// Test-only Windows input helper. Compile into a temporary directory, not REAPER.
// Down/wheel events require the foreground window and cursor to belong to the
// supplied REAPER FX window. Up events always release a test-held button safely.
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

public static class CCScopeUIInput
{
    [StructLayout(LayoutKind.Sequential)] public struct Point { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] public struct MouseInput
    {
        public int dx, dy;
        public uint mouseData, dwFlags, time;
        public UIntPtr dwExtraInfo;
    }
    [StructLayout(LayoutKind.Sequential)] public struct Input
    {
        public uint type;
        public MouseInput mi;
    }
    [DllImport("user32.dll")] static extern bool IsWindow(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool IsChild(IntPtr parent, IntPtr child);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool GetCursorPos(out Point p);
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(Point p);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll", SetLastError=true)] static extern uint SendInput(uint count, Input[] inputs, int size);

    public static int Main(string[] args)
    {
        if (args.Length < 2) return 1;
        long address;
        if (!long.TryParse(args[0], out address)) return 1;
        IntPtr root = new IntPtr(address);
        string action = args[1];
        bool release = action == "left-up" || action == "right-up";
        uint flags;
        uint data = 0;
        switch (action)
        {
            case "left-down": flags = 0x0002; break;
            case "left-up": flags = 0x0004; break;
            case "right-down": flags = 0x0008; break;
            case "right-up": flags = 0x0010; break;
            case "wheel":
                int delta;
                if (args.Length != 3 || !int.TryParse(args[2], out delta)) return 1;
                flags = 0x0800; data = unchecked((uint)delta); break;
            default: return 1;
        }
        if (!release)
        {
            uint pid;
            Point p;
            if (!IsWindow(root) || GetWindowThreadProcessId(root, out pid) == 0
                || !String.Equals(Process.GetProcessById((int)pid).ProcessName, "reaper", StringComparison.OrdinalIgnoreCase)) return 2;
            IntPtr top = GetAncestor(root, 2); // GA_ROOT, not the popup's owner.
            SetForegroundWindow(top);
            if (GetForegroundWindow() != top || !GetCursorPos(out p)) return 2;
            IntPtr hit = WindowFromPoint(p);
            if (hit != root && !IsChild(root, hit)) return 3;
        }
        Input[] input = { new Input { type = 0, mi = new MouseInput { dwFlags = flags, mouseData = data } } };
        if (SendInput(1, input, Marshal.SizeOf(typeof(Input))) != 1) return 4;
        Console.WriteLine("input-ok");
        return 0;
    }
}
