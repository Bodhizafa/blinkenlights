# Blinkenlights
So the idea here is to define a specification that covers the functionality a wide variety of the sorts of things we want to have, and a useful subset of can be implemented in a reasonable language in half an hour. This eliminates the need for a shared runtime/library/codebase/anything. It will run over TCP/IP, so all of said things can be on the same network, perhaps via wifi, or across the country and still work. Let's call it CAMP - CAMP Automation and Management Protocol, cause my fursona is windows 98, and also because fuck you.

## Wire protocol
Nodes come in two flavors, speaking and listening. A listening node opens a listen socket and awaits commands. A speaking node connects to a listening node and issues commands. A single thing may be both a listening and speaking node, and may listen or speak to multiple nodes, including ones on itself (presumably through the loopback interface). Lots of hardware can be multiplexed onto one node, but doesn't have to be (i.e. a thing with a bunch of lights and buttons and poofers can be one node with a bunch of channels)
Every listening node must implement 'reset' and 'create channel', but other than that should only bother with the subset of things they support. Commands a node doesn't implement, as well as extra data in the packet body (when allowed, Some commands have a variable length argument, which is to be assumed to be the rest of the packet) must be ignored.

Packet format:
```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Total length in bytes (32 bits)                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Channel (16 bits)             |  Command (16 bits)            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
/ Body (variable length, no specific alignment)                 /
/                                                               /
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
Total length includes itself so the smallest packet possible (no body) is 64 bits with a total length of 8.
A speaking node consists of any piece of software that is capable of communicating with listening nodes.
A listening node consists of 2^16 conceptual "channels", each of which has a 'type' associated with it, said type is assigned via the 'create channel' command available on type 0 channels. 
All channels are initialized to type 0 after a reset, except channel 0xFFFF, which is initialized to type 0xFFFF and is used for high-level control of the node itself, whereas individual channels are for individual peripherals (for example, one button is a channel, one poofer is a channel, one strand of WS28xx is a channel, the vibrating motor in the dildo that's usually stored in Kevin is a channel, etc)
Various commands (such as Interrupting Input configuration) will cause a listening node to 'become' a speaking node as well.
What commands are available and body structure depends on the type of the channel being addressed.
### Channel type 0x0 - Unassigned
This channel type doesn't support doing anything other than being initialized to something else.
#### Creation args
N/A
#### Command 0x01 - Create Channel
Body format:
```
 0                   1          
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Type (16 bits)                |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
/ Creation args                 /
/ (length depends on type)      /                                                              /
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
Turns this channel into the type of channel given, see individual channel types for creation args. Once a channel has been created, it cannot be changed to a different type without a reset.
### Channel type 0x1 - Lights
This channel type is for controlling strings of WS28xx and other 1-wire serial LEDs
#### Creation args
```
 0                   1          
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Length                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Format        | Speed         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Pin                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

Length is the number of LEDs, 
Format is an enum for the color format of the output, 0 = GRB, 1 = RGB, there are probably more.
Speed is an enum for PWM speed, IIRC ours use 800KHz, 400Hz ones exist, some can be 'overclocked' a bit.
Pin is which GPIO on the node the lights are attached to.
#### Command 0x01 - Frame Data
```
 0                   1                   2
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| R             | G             | B             |
/ ... Strand length times                       /
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
Sets the color of the lights
#### Command 0x02 - Blank (optional)
```
No body data
```
Sets this light strand to off.

#### Command 0x03 - Test (optional)
```
No body data
```
Makes this light strand flash garish colors for easy identification in the field

### Channel type 0x02 - Output
A single pin that can be HIGH or LOW. Comes with a configured max fire time such that the pin must never be held HIGH for longer than said fire time (regardless of command sequence). In the event that it is, the node should report an error and this channel must be set low and disabled until a reset. For analog pins with a max fire time, any nonzero intensity counts as HIGH.
#### Creation args
```
 0                   1          
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Pin                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Max Fire time (ms)            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|I|T|O|ADP|                     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
Max Fire Time is an endpoint-enforced maximum time for the given output to be on 0 means unlimited.
I: Set to invert the output (has no effect on continuous outputs)
T: Set to modulate tri-state registers rather than port registers
O: Value to set port or tri-state (whichever isn't being modulated) to permanately
ADP: 0: digital, 1: full D/A, 2: PWM
(If a pin is set to D/A that doesn't support it, a node should log an error and must disable the given channel)

#### Command 0x01 - Fire
```
 0                   1          
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Fire Time (ms)                |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Intensity                     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
Sets the configured pin to the given intensity value if D/A or PWM, if digital, intensity is ignored

#### Command 0x02 - Set
```
 0                   1          
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Intensity                     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
Sets the configured pin to Intensity, if digital, sets it to HIGH, regardless of intensity
#### Command 0x03 - Unset
```
No body data
```
Sets the configured pin to LOW.

### Channel type 0x03 - Interrupting Digital Input
A single pin configured as a digital input. It will send messages when they change or reach a given state to each given target.
#### Creation args
```
 0                   1          
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Pin                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
#### Command 0x01 - Add Target
```
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|R|F|O|I|                       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Target host IP                |
|                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Target channel                |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Target command                |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Target payload                |
/ .. variable length            /
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
R: Set to trigger on rising edge
F: Set to trigger on falling edge
O: Set to trigger only once
I: Set to trigger if the pin is already in the given state (low for F, high for R)
Note there are combinations of R/F/I that don't make sense (for example setting all of them will unconditionally dispatch an event, setting both R and F low will never dispatch, setting both R and F high will make it impossible to distinguish from press/release of a button, etc). This is fine.
Target host/channel/command/payload: When the set changes according to R/F/I, a message will be dispatched to the given host on the given channel with the given command and payload. The idea here is to be able to point buttons at other nodes' outputs without requiring an intermediary computer.
Target host being 127.0.0.1 must work right on nodes with both inputs and output.

#### Command 0x02 - Remove Target (optional)
```
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Target host IP                |
|                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
Remove all set up actions pointed at the given target.
### Channel type 0x04 - Continuous Interrupting Input
TODO - These get complicated (Are we monitoring a value or a rate, what do we do about continuous knobs that have a discontinuity at 360-0, Should we use floating point or fixed, how do we scale things either way, non-digital non-analog continuous inputs can speak many protocols and take many different numbers of pins, not going to specify this one until we have a real-world use for it, and ideally some working implementations of the simpler types.
### Channel type 0x05 - Continuous Logging Input
TODO - Similar to digital interrupting input, but instead of waiting for an event, just sends the value of some sensor at a configurable interval to a configurable target. Has a lot of the same challenges as Continuous Interrupting Input
### Channel type 0xFFFF - Node metadata control
This channel type can't be created, but channel 0xFFFF is always one of these.
#### Command 0x01 - Reset
```
No body data
```
Resets the node to the initial state. All chanel-specific state should be deleted, and all channels (except 0xFFFF) set back to type 0x00
#### Command 0x02 - Set reporting host
```
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Target host IP                |
|                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
Sets the host that this node will send Log Report messages to (reports always go to channel 0xFFFF as Log report messages)
#### Command 0x03 - Log report
```
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
/ ASCII-encoded cstring         /
/ ...                           /
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
This will be emitted by nodes to their reporting host in the event of errors/whatever
#### Command 0x04 - Identify
```
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Target host IP                |
|                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
This will cause the node to send a 'Log report' about itself to the given host.

## Node proposals
a Node on the network is either a piece of software running on a computer connected to the network, or some hardware/installation/whatever that is ostensibly some embedded SoC/MCU/dev board/'dweeno/whatever also attached to the network, presumably each running different implementations of this protocol. Not all nodes should implement all functionality (indeed, one node which implements everything here wouldn't really make much sense). Here I'm going to enumerate everything I was keeping in mind when writing the above wire protocol. I don't have time to build all these things myself, at least not this year, but hey, I can dream, right?
* Thing 1: A beaglebone and a bunch of lights, speaks this protocol on a listening socket. Implements 'Lights' channel type. (Also known as the synaq hardware)
* Thing 2: My dusty-ass T520 running the synaq model. Connects to something that implements the 'Lights' channel type, and outputs frame data. Also listens for the Log report command.
* Thing 3: Similar to thing 1 but controls the spectrum dome
* Thing 4: Ahoat's shiny-ass macbook listening to music and running spectrum. Probably implements a whole bunch of channel types corresponding to different implementations of the spectrum Input and Output interfaces.
* Thing 5: A 'dweeno or something with some relays big enough to run solenoids, implements the 'Digital output' channel type. (Also known as the whyfi)
* Thing 6: A 'dweeno or something some buttons, implements the 'Interrupting Input' channel types, (Also known as the whyfi control pane; and the synaq one too)
* Thing 7: A sensor that monitors the power grid draw by various things, implements the 'Continuous Logging Input' channel type. (Weather sensor? Wind sensor? Strange knob way the fuck in nowhere for hippies to play with?)
* Thing 8: A program running on my beefy ass desktop that implements 'Lights' and displays a simulation on the screen. Perhaps derived from the spectrum simulator.
* Thing 10: A bridge to IoT light bulbs, implements listening lights channels, translates them to whatever the fuck protocol those infernal things use.
* Thing 11: A giant rolling ball you can hang out in with an IMU on it, implements 'Continuous interrupting input' on 9 channels (one per DOF)
* Thing 12: An actual dildo. Implements the 'Output' channel type
