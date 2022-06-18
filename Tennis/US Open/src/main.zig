const std = @import("std");

pub const io_mode = .evented;

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

    fn handle(self: *Client) !void {
        defer {
            self.stream.close();
        }
        while (true) {
            const message = self.read_message() catch |err| {
                std.log.info("Client Lost: {any}\n", .{err});
                return;
            };
            
            std.debug.print("Internet!: {any}\n", .{message});
        }
    }
};

pub fn main() anyerror!void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    var allocator = gpa.allocator();
    var server = std.net.StreamServer.init(.{ .reuse_address = true });
    defer server.deinit();
    try server.listen(std.net.Address.parseIp("127.0.0.1", 42024) catch unreachable);
    std.log.info("Listening on {}\n", .{server.listen_address});
    std.debug.print("Alloc: {any}", .{allocator});
    while(true) {
        const client = try allocator.create(Client);
        client.* = Client {
            .stream = (try server.accept()).stream,
            .allocator = allocator,
        };
        _ = async client.handle();
    }
}
