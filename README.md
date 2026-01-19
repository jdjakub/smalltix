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

# BlockClosure Example
You will find that `aCanvas` is a `DummyCanvas`:

```bash
./send aCross drawOn- aCanvas
```

Output:

```
...
[ CANVAS COMMAND ]: aCanvas fillRectangle: new/aRectangle_123 color: int/255
...
[ CANVAS COMMAND ]: aCanvas fillRectangle: new/aRectangle_456 color: int/255
nil
```
...along with 14 new objects :)

My dummy source code for `drawOn:` includes a block closure:

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

The intended order of params here is: outer temps, outer args, inner block temps (here there are none) and inner block args (`each`).

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

# Implementation notes
All objects have an inst var `class`. An underscore e.g. `_elements` means it's not really an instance variable whose contents conforms to Smalltix conventions; i.e. its contents might not be an object reference. (For example, `anArray/_elements` is a space-separated list of references.)

# ST2bash
Check out the Smalltalk-to-Bash compiler generated for me by Claude Opus. Currently it should be able to match all my hand-compiled examples (excluding BlockClosures). Open problems it raises:

- How to represent references to string literals?
