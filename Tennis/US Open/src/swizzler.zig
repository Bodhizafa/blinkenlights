const std = @import("std");
const ArrayList = std.ArrayList;

pub const Color = struct {
    red: u8 = 0, 
    green: u8 = 0, 
    blue: u8 = 0
};

pub const ColorList = ArrayList(Color);

pub const PixelBuffers = struct {
    channel_bufs: [8]ColorList,
    lock: std.Thread.Mutex,
    pub fn init(allocator: std.mem.Allocator) PixelBuffers {
        var channel_bufs: [8]ColorList = .{undefined} ** 8;
        var i: usize = 0;
        while (i < 8) : (i += 1) {
            channel_bufs[i] = ColorList.init(allocator);
        }
        return PixelBuffers{
            .channel_bufs = channel_bufs,
            .lock = std.Thread.Mutex{}
        };
    }

    pub fn deinit(self: *PixelBuffers) void {
        for (self.channel_bufs) |list| {
            list.deinit();
        }
    }

    pub fn update(self: *PixelBuffers, channel: u8, offset: u16, new_data: [] const Color) !void{
        if (channel > 8 or channel == 0) {
            std.log.err("Illegal channel: {d}", .{channel});
            return;
        }
        std.debug.print("\nAdding {d} pixels to channel {d}, offset {d}", .{new_data.len, channel, offset});
        self.lock.lock();
        defer self.lock.unlock();
        var channel_buf = &self.channel_bufs[channel-1];
        if (offset + new_data.len > channel_bufs.items.len) {
            try channel_buf.resize(offset + new_data.len);
        }
        try channel_buf.replaceRange(offset, new_data.len, new_data);
    }

    pub fn output(self: *PixelBuffers, allocator: std.mem.Allocator) !ArrayList(u8) {
        var max_length:usize = 0;
        self.lock.lock();
        defer self.lock.unlock();
        for (self.channel_bufs) |channel_buf| {
            max_length = std.math.max(max_length, channel_buf.items.len);
        }
        std.debug.print("\nMax Length: {d}", .{max_length});
        var out =  try ArrayList(u8).initCapacity(allocator, max_length * 8 * 3 + 2);
        try out.append(0x00);  // Lead-in. I saw a first clock get dropped once, maybe
        try out.append(0xFF);  // Begin

        var i: usize = 0;
        while (i < max_length) : (i += 1) {
            var pixels =  [_]Color{
                Color{.red = 0, .green = 0, .blue = 0},
            } ** 8;
            var j: u4 = 0;
            while (j < 8) : (j += 1) {
                if (self.channel_bufs[j].items.len >= max_length) {
                    pixels[j] = self.channel_bufs[j].items[i];
                }
            }
            j = 0;
            while (j < 8) : (j += 1) {
                const shift = 7 - j;
                const mask: u16 = @as(u16, 1) << shift;
                try out.append(@intCast(u8,
                    (((pixels[0].red & mask) >> shift) << 0)|
                    (((pixels[1].red & mask) >> shift) << 1)|
                    (((pixels[2].red & mask) >> shift) << 2)|
                    (((pixels[3].red & mask) >> shift) << 3)|
                    (((pixels[4].red & mask) >> shift) << 4)|
                    (((pixels[5].red & mask) >> shift) << 5)|
                    (((pixels[6].red & mask) >> shift) << 6)|
                    (((pixels[7].red & mask) >> shift) << 7)));
            }
            j = 0;
            while (j < 8) : (j += 1) {
                const shift = 7 - j;
                const mask: u16 = @as(u16, 1) << shift;
                try out.append(@intCast(u8,
                    (((pixels[0].green & mask) >> shift) << 0)|
                    (((pixels[1].green & mask) >> shift) << 1)|
                    (((pixels[2].green & mask) >> shift) << 2)|
                    (((pixels[3].green & mask) >> shift) << 3)|
                    (((pixels[4].green & mask) >> shift) << 4)|
                    (((pixels[5].green & mask) >> shift) << 5)|
                    (((pixels[6].green & mask) >> shift) << 6)|
                    (((pixels[7].green & mask) >> shift) << 7)));
            }
            j = 0;
            while (j < 8) : (j += 1) {
                const shift = 7 - j;
                const mask: u16 = @as(u16, 1) << shift;
                try out.append(@intCast(u8,
                    (((pixels[0].blue & mask) >> shift) << 0)|
                    (((pixels[1].blue & mask) >> shift) << 1)|
                    (((pixels[2].blue & mask) >> shift) << 2)|
                    (((pixels[3].blue & mask) >> shift) << 3)|
                    (((pixels[4].blue & mask) >> shift) << 4)|
                    (((pixels[5].blue & mask) >> shift) << 5)|
                    (((pixels[6].blue & mask) >> shift) << 6)|
                    (((pixels[7].blue & mask) >> shift) << 7)));
            }
        }
        return out;
    }
};

const test_allocator = std.testing.allocator;
test "lead in" {
    var snarbledina = PixelBuffers.init(test_allocator);
    std.debug.print("All your codebase are belong to us.", .{});
    defer snarbledina.deinit();
    const out = try snarbledina.output(test_allocator);
    defer out.deinit();
    try std.testing.expectEqualSlices(u8, &[_]u8{0x00, 0xFF}, out.items);
}

test "CH1" {
    var snarbledina = PixelBuffers.init(test_allocator);
    defer snarbledina.deinit();
    try snarbledina.update(1, 0, &[_]Color{Color{.red = 0xFF, .green = 0xFF, .blue = 0xFF}});
    const out = try snarbledina.output(test_allocator);
    defer out.deinit();
    try std.testing.expectEqualSlices(u8, &[_]u8{0x00, 0xFF,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,

        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,

        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
        0b00000001,
    }, out.items);
}

test "CH2" {
    var snarbledina = PixelBuffers.init(test_allocator);
    defer snarbledina.deinit();
    try snarbledina.update(2, 0, &[_]Color{Color{.red = 0b10100101, .green = 0b01011010, .blue = 0b10101010}});
    const out = try snarbledina.output(test_allocator);
    defer out.deinit();
    try std.testing.expectEqualSlices(u8, &[_]u8{0x00, 0xFF,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,

        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,

        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,
    }, out.items);
}

test "Long" {
    var snarbledina = PixelBuffers.init(test_allocator);
    defer snarbledina.deinit();
    try snarbledina.update(2, 0, &[_]Color{
        Color{.red = 0b10100101, .green = 0b01011010, .blue = 0b10101010},
        Color{.red = 0b11001100, .green = 0b10101010, .blue = 0b00000000},
    });
    const out = try snarbledina.output(test_allocator);
    defer out.deinit();
    try std.testing.expectEqualSlices(u8, &[_]u8{0x00, 0xFF,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,

        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,

        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,

        0b00000010,
        0b00000010,
        0b00000000,
        0b00000000,
        0b00000010,
        0b00000010,
        0b00000000,
        0b00000000,

        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,
        0b00000010,
        0b00000000,

        0b00000000,
        0b00000000,
        0b00000000,
        0b00000000,
        0b00000000,
        0b00000000,
        0b00000000,
        0b00000000,
    }, out.items);
}
