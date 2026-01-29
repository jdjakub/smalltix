Works on Windows WSL Ubuntu, because colons in message names get mangled to dash: e.g. `doSomethingWith:and:andAlso:` becomes `doSomethingWith-and-andAlso-`.

# Install requirements
Requires `bc` for bash arithmetic:

```bash
sudo apt install bc
```

st2bash Compiler and websocket canvas require python3.

Examples center around `SBECrossMorph` from Squeak By Example 6.0.

# Simple Send Example

```bash
aRect=$(./send aCross horBar)
```

Inspect `$aRect` in your file browser... (or do `./send $aRect printString`)

It should be among 4 new objects (directories) created.

Two are its points, one was a temporary point that ought to be garbage collected. (I suggest "Move to Recycle Bin"...)

Note: to enable thorough `set -x` tracing in the Bash scripts (e.g. to debug an error), set `DEBUG`:

```bash
DEBUG=t ./send aCross horBar
```

# Drawing via WebSocket Canvas Example
Setup: `pip install websockets`.

Start server: `web-canvas/server.py`

Open the client `web-canvas/smalltix.html` in a web browser. Should say `Connected to WebSocket server` in the JS console.

`aCanvas` is a `WebCanvas`.
- Connect canvas: `./send aCanvas connect`
- Draw: `./send aCross drawOn- aCanvas`
- Sometime later, disconnect (to kill the forwarder process in `aCanvas/_wsPid`): `./send aCanvas disconnect`

```smalltalk
SBECrossMorph >> drawOn: aCanvas
  (Array with: self horBar with: self verBar) do: [ :rect |
    aCanvas fillRectangle: rect color: self color.
    ]
```

`WebCanvas/methods/fillRectangle-color-` sends JSON Canvas commands to the server, to forward to the client, to execute on the `<canvas>` element; e.g.

```
{ "method": "fillStyle", "value": 255 }
{ "method": "fillRect", "params": [10, 10, 300, 200] }
```

Currently, colours (`aCross/color`) are just tagged ints converted to a CSS hex colour code: e.g. `int/255 -> #0000ff`. Colours-as-objects can come later.

![SBECrossMorph drawing clip](./SBECrossMorph-drawOn.gif)

It only takes 5 seconds to draw two rectangles! Just imagine what it will be like on the hardware of tomorrow, in the year 2000, or even later!

```
real    0m3.329s (mostly spent waiting for filesystem and process synchronisation)
user    0m0.526s
sys     0m0.261s
```

These figures imply that with FUSE and userspace exec optimisation it could take as little as 0.8 seconds to draw the rectangles ... lol

# Nested BlockClosures Example

```Smalltalk
SBECrossMorph >> drawOnMessy: aCanvas
  | topAndBottom1 topAndBottom2 topAndBottoms |
  topAndBottom1 := Array with: (self bounds) with: (Rectangle origin: 0@0 corner: 100@100).
  topAndBottom2 := Array with: (self bounds) with: (Rectangle origin: 100@100 corner: 200@200).
  topAndBottoms := Array with: topAndBottom1 with: topAndBottom2.
  topAndBottoms do: [:eachArray |
      | myTemp |
      myTemp := 3.
      eachArray do: [:each | aCanvas fillRectangle: each color: self color].
  ].
```

I think I've got it to perform correctly on this sort of thing.

Do the following:

```bash
./send aCross drawOnMessy- aDummyCanvas
```

Output:

```
[ CANVAS COMMAND ]: aDummyCanvas fillRectangle: boundsRect color: int/255
[ CANVAS COMMAND ]: aDummyCanvas fillRectangle: new/aRectangle_123 color: int/255
[ CANVAS COMMAND ]: aDummyCanvas fillRectangle: boundsRect color: int/255
[ CANVAS COMMAND ]: aDummyCanvas fillRectangle: new/aRectangle_456 color: int/255
nil
```
...along with a ton of new objects under `_new/` :)

# Single BlockClosure example

My earlier dummy source code for `drawOn:` included a non-nested block closure:

```smalltalk
SBECrossMorph >> drawOn: aCanvas
  | topAndBottom |
  topAndBottom := Array with: (self bounds) with: (Rectangle origin: 0@0 corner: 100@100).
  topAndBottom do: [:each | aCanvas fillRectangle: each color: self color].
```

I think my block closure handling is correct. We rewrite the above as:

```smalltalk
SBECrossMorph >> drawOn: aCanvas
  | topAndBottom |
  topAndBottom := Array with: (self bounds) with: (Rectangle origin: 0@0 corner: 100@100).
  block1 := BlockClosure fromCode: ⟦SBECrossMorph/methods/drawOn-~block1⟧
                         with: #(self topAndBottom aCanvas).
  topAndBottom do: block1
```

Where the fancy brackets `⟦SBECrossMorph/methods/drawOn-~block1⟧` denote the insertion of a raw Smalltix method address, not normally allowed in source code. We extract the block body to this new pseudo-method and compile it:

```smalltalk
"SBECrossMorph/methods/drawOn-~block1"
_method: topAndBottom and: aCanvas and: each
    aCanvas fillRectangle: each color: self color
```

The intended order of params here is: outer temps, outer args, and inner block args (`each`).

`block1` will look like this:

```
block1/
  |-    class = BlockClosure
  |-    _code = SBECrossMorph/methods/drawOn-~block1
  |- bindings = someArray
                   |
someArray/    <----+
  |-     class = Array
  |- _elements = "aCross   rectArray  aCanvas"
                (  self  topAndBottom aCanvas )
                              |
rectArray/    <---------------+
  |-     class = Array
  |- _elements = "boundsRect someOtherRect"
```

# Early Returns

```smalltalk
Array >> containsInstanceOf: aClass
  self do: [ :elem | (elem isKindOf: aClass) ifTrue: [^true] ].
  ^false
```

The early return `^true` is inside a block inside a block. Here's what we do. Create the block as above. Then, before the `do:` send, we need this:

```bash
# Block contains early return; infra needed
# Export file path to all descendants
export SMALLTIX_RETURN_FILE="/tmp/smalltix_return_$$"

smalltix_handle_return() {
  if [[ -s $SMALLTIX_RETURN_FILE ]]; then
    cat $SMALLTIX_RETURN_FILE
    rm -f "$SMALLTIX_RETURN_FILE"
    exit 0
  else
    exit 2
  fi
}
trap 'smalltix_handle_return' ERR
trap 'rm -f "$SMALLTIX_RETURN_FILE"' EXIT

_=$(./send $self do- $block)
echo false
```

The code for the outer block is compiled normally; it needn't concern itself with the early return at all. The code for the inner block looks like this:

```bash
echo true > $SMALLTIX_RETURN_FILE
exit 1 # Trigger cascading ERR (-e) in supershells
```

It should have inherited the env var from the export, which will be a path to the return file for the method activation's PID (e.g. `/tmp/smalltix_return_1234`). It writes the return value `true` to the file, and exits with an error value. The enclosing `$(...)` supershell, which should have inherited `set -e` (`set -e` and `export SHELLOPTS` in `./send` is essential for this), will see this error and propagate it all the way up immediately, eventually running into the `ERR` handler in the method. This will `cat` the return value from the file to stdout, "returning" it in Smalltix at the correct point, delete the file, and exit successfully with 0 (so as to not trigger further `ERR`s). If some "real" shell script error happened, I assume the return file didn't get written (not watertight, I know) and cascade the error as code 2 (ensuring the entire send tree back to the root blows up). Finally, if nobody did an early return after all, the return file will be deleted on exit.

Try `./send anArray containsInstanceOf- Rectangle` or `./send anArray containsInstanceOf- Roctongal`.

# Blocks in Terminal
Warning: speculation

```smalltalk
anArray do: [ :each | each isInstanceOf: Rectangle ].
```

```bash
./send anArray do- $(./blk 'each=$1; ./send $each isInstanceOf- Rectangle')
```

# Implementation notes
All objects have an inst var `class`. An underscore e.g. `_elements` means it's not really an instance variable whose contents conforms to Smalltix conventions; i.e. its contents might not be an object reference. (For example, `anArray/_elements` is a space-separated list of references.) `_code` is underscored to be safe because, while I ought to treat an executable file like a method object, I don't have that working yet.

`true` is a `BoolTrue` and `false` is a `BoolFalse` because Windows filenames are case insensitive 🙃

# ST2bash
Check out the Smalltalk-to-Bash compiler generated for me by Claude Opus. Currently it should be able to match all my hand-compiled examples. It's currently motivating the following questions:

- How to represent references to string literals?
