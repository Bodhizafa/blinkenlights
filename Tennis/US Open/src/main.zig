const std = @import("std");
const swizzler = @import("swizzler.zig");
const c = @cImport({
    @cInclude("sys/ioctl.h");
    @cInclude("linux/spi/spidev.h");
});

//pub const io_mode = .evented;

const Command = enum(u8) {
    COLORS_8BIT = 0x00,
    COLORS_16BIT = 0x02,
    SYSEX = 0xFF,
};

const Message = struct {
    channel: u8,
    command: Command,
    data: []const u8,
};

const ClientError = error {
    Disconnected
};

pub const Server = struct {
    pixel_buffers: swizzler.PixelBuffers,
    spi: std.fs.File,
    allocator: std.mem.Allocator,
    stream_server: std.net.StreamServer,
    pub fn init(spi_filename: [] const u8, listen_address: std.net.Address, allocator: std.mem.Allocator) !Server {
        var stream_server = std.net.StreamServer.init(.{ .reuse_address = true });
        try stream_server.listen(listen_address);
        std.log.info("Listening on {}\n", .{stream_server.listen_address});
        return Server {
            .pixel_buffers = swizzler.PixelBuffers.init(allocator),
            .spi = try std.fs.openFileAbsolute(spi_filename, std.fs.File.OpenFlags{.mode = std.fs.File.OpenMode.write_only}),
            .allocator = allocator,
            .stream_server = stream_server,
        };
    }
    pub fn run_net(self: *Server) !void {
        std.log.info("Network loop started",.{});
        while (true) {
            var client = Client {
                .stream = (try self.stream_server.accept()).stream,
                .allocator = self.allocator,
            };
            defer client.deinit();
            std.log.info("Client Found.\n", .{});
            while (true) {
                const message = client.read_message() catch |err| {
                    std.log.info("Client Lost: {any}\n", .{err});
                    break;
                };
                try self.pixel_buffers.update(message.channel, 0, @ptrCast([]swizzler.Color, message.data));
                try self.output();
            }
        }
    }
    pub fn output(self: *Server) !void {
        const tx = try self.pixel_buffers.output(self.allocator);
        defer tx.deinit();
        const ioctl_no = @intCast(u32, c._IOW(c.SPI_IOC_MAGIC, 0, [c.SPI_MSGSIZE(1)]u8));
        const transfer = [1]c.spi_ioc_transfer{.{
            .tx_buf = @ptrToInt(&tx.items),
            .rx_buf = 0,
            .len = @intCast(u32, @minimum(tx.items.len, 4096)),
            .delay_usecs = 0,
            .speed_hz = 6666666,
            .bits_per_word = 8,
            .cs_change = 0,
            .tx_nbits = 0,
            .rx_nbits = 0,
            .pad = 0,
        }};
        const ret = c.ioctl(self.spi.handle, @bitCast(c_int, ioctl_no), &transfer);
        if (ret == -1) {
            std.log.err("IOCTL {d} returned {d}\n",
                .{
                    ioctl_no,
                    ret,
                }
            );
        }
    }
    pub fn deinit(self: *Server) void{
        self.pixel_buffers.deinit();
        self.spi.deinit();
        self.lock.deinit();
        self.stream_server.deinit();
    }
};

pub const Client = struct {
    stream: std.net.Stream,
    allocator: std.mem.Allocator,
    fn read_message(self: *Client) !Message {
        const header_len = 4;
        var header_buf: [4]u8 = .{0} ** 4;
        var cur_idx: usize = 0;
        while (cur_idx < header_len) {
            const new_read_len = try self.stream.read(header_buf[cur_idx..header_len]);
            if (new_read_len == 0) {
                return ClientError.Disconnected;
            }
            cur_idx += new_read_len;
        }
        const channel = header_buf[0];
        const command = header_buf[1];
        cur_idx = 0;
        const data_len: usize = std.mem.readIntBig(u16, header_buf[2..4]);
        std.debug.print("Channel: {d}. Command: {d}. Data len: {d}. Alloc: {any}\n",
            .{channel, command, data_len, self.allocator});
        const data_buf = try self.allocator.alloc(u8, data_len);
        while (cur_idx < data_len) {
            const new_read_len = try self.stream.read(data_buf[cur_idx..data_len]);
            if (new_read_len == 0) {
                return ClientError.Disconnected;
            }
            cur_idx += new_read_len;
        }
        std.debug.print("Data: {any}\n", .{data_buf});
        return Message{
            .channel = channel,
            .command = try std.meta.intToEnum(Command, command),
            .data = data_buf,
        };
    }
    pub fn deinit(self: *Client) void {
        self.stream.close();
    }

};

pub fn main() anyerror!void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    var allocator = gpa.allocator();
    const addr: std.net.Address = std.net.Address.parseIp("0.0.0.0", 7890) catch unreachable;
    std.log.info("Attempting to bind {any}", .{addr});
    var server = try Server.init("/dev/spidev0.0", addr, allocator);
    try server.run_net();
}
