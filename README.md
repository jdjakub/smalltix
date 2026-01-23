Works on Windows WSL Ubuntu, because colons in message names get mangled to dash: e.g. `doSomethingWith:and:andAlso:` becomes `doSomethingWith-and-andAlso-`. Requires `bc` for bash arithmetic:

```bash
sudo apt install bc
```

Examples: `SBECrossMorph` from Squeak By Example 6.0.

# Simple Send Example

```bash
aRect=$(./send aCross horBar)
```

Inspect `$aRect` in your file browser...

It should be among 4 new objects (directories) created.

Two are its points, one was a temporary point that ought to be garbage collected. (I suggest "Move to Recycle Bin"...)

# Nested BlockClosures Example

```Smalltalk
SBECrossMorph >> drawOn: aCanvas
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

You will find that `aCanvas` is a `DummyCanvas` (`cat aCanvas/class`). Do the following:

```bash
./send aCross drawOn- aCanvas
```

Output:

```
[ CANVAS COMMAND ]: aCanvas fillRectangle: boundsRect color: int/255
...
[ CANVAS COMMAND ]: aCanvas fillRectangle: new/aRectangle_123 color: int/255
...
[ CANVAS COMMAND ]: aCanvas fillRectangle: boundsRect color: int/255
...
[ CANVAS COMMAND ]: aCanvas fillRectangle: new/aRectangle_456 color: int/255
nil
```
...along with a ton of new objects under `new/` :)

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
  cat $SMALLTIX_RETURN_FILE
  rm -f "$SMALLTIX_RETURN_FILE"
  exit 0
}
trap 'smalltix_handle_return' ERR

_=$(./send $self do- $block)
printf false
```

The code for the outer block is compiled normally; it needn't concern itself with the early return at all. The code for the inner block looks like this:

```bash
printf true > $SMALLTIX_RETURN_FILE
exit 1 # Trigger cascading ERR (-e) in supershells
```

It should have inherited the env var from the export, which will be a path to the return file for the method activation's PID (e.g. `/tmp/smalltix_return_1234`). It writes the return value `true` to the file, and exits with an error value. The enclosing `$(...)` supershell, which should have inherited `set -e` (`set -e` and `export SHELLOPTS` in `./send` is essential for this), will see this error and propagate it all the way up immediately, eventually running into the `ERR` handler in the method. This will `cat` the return value from the file to stdout, "returning" it in Smalltix at the correct point, delete the file, and exit successfully with 0 (so as to not trigger further `ERR`s). TODO: must gracefully handle REAL "errors" that don't write to the return file

Try `./send anArray containsInstanceOf- Rectangle` or `./send anArray containsInstanceOf- Roctongal`.

# Implementation notes
All objects have an inst var `class`. An underscore e.g. `_elements` means it's not really an instance variable whose contents conforms to Smalltix conventions; i.e. its contents might not be an object reference. (For example, `anArray/_elements` is a space-separated list of references.) `_code` is underscored to be safe because, while I ought to treat an executable file like a method object, I don't have that working yet.

# ST2bash
Check out the Smalltalk-to-Bash compiler generated for me by Claude Opus. Currently it should be able to match all my hand-compiled examples. It's currently motivating the following questions:

- How to represent references to string literals?
