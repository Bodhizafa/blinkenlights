const std = @import("std");
const c = @cImport({
    @cInclude("sys/ioctl.h");
    @cInclude("linux/spi/spidev.h");
});
const ioctl = c.ioctl;

pub fn main() !void {
    const allocator = std.heap.page_allocator;
    const stdout = std.io.getStdOut().writer();
    const f = try std.fs.openFileAbsolute("/dev/spidev0.0", std.fs.File.OpenFlags{.mode = std.fs.File.OpenMode.write_only});
    // zig translate-c doesn't get this macro right
    const ioctl_no = @intCast(u32, c._IOW(c.SPI_IOC_MAGIC, 0, [c.SPI_MSGSIZE(1)]u8));
    // 2908 is the max for 1 xfer on raspi
    // 4096 on jetson
    const tx_len = 4096;
    const tx = try allocator.alloc(u8, tx_len);
    var i: u32 = 0;
    while (i < tx_len): (i += 1) {
        tx[i] = 0xA5;
    }
    const transfer = [1]c.spi_ioc_transfer{.{
        .tx_buf = @ptrToInt(&tx),
        .rx_buf = 0,
        .len = tx_len,
        .delay_usecs = 0,
        .speed_hz = 6666666,
        .bits_per_word = 8,
        .cs_change = 0,
        .tx_nbits = 0,
        .rx_nbits = 0,
        .word_delay_usecs = 0,
        .pad = 0,
    }};
    const ret = c.ioctl(f.handle, @bitCast(c_int, ioctl_no), &transfer);
    try stdout.print("IOCTL {d} returned {d}\n",
        .{
            ioctl_no,
            ret,
        }
    );
}
