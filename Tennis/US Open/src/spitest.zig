const std = @import("std");d
const spidev = @import("spidev.zig");
const ioctl = @cImport({
    @cInclude("sys/ioctl.h");
});


pub fn main() !void {
    const stdout = std.io.getStdOut().writer();
    const f = try std.fs.openFileAbsolute("/dev/spidev0.0", std.fs.File.OpenFlags{.mode = std.fs.File.OpenMode.write_only});
    const ioctl_no = spidev._IOW(spidev.SPI_IOC_MAGIC, 0, [spidev.SPI_MSGSIZE(1)]u8);
    const tx = [_]u8{0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};
    const transfer: spidev.spi_ioc_transfer = .{
        .tx_buf = @ptrToInt(&tx),
        .rx_buf = 0,
        .len = 10,
        .delay_usecs = 0,
        .speed_hz = 7000000,
        .bits_per_word = 0,
        .cs_change = 0,
        .tx_nbits = 0,
        .rx_nbits = 0,
        .word_delay_usecs = 0,
        .pad = 0,
    };
    const ret = ioctl.ioctl(f.handle, @bitCast(c_int, ioctl_no), &transfer);
    try stdout.print("IOCTL {d} returned {d}\n",
        .{ioctl_no, ret}
    );
}
