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
[ CANVAS COMMAND ]: aCanvas fillRectangle: obj4 color: int/255
...
[ CANVAS COMMAND ]: aCanvas fillRectangle: obj8 color: int/255
nil
```
...along with 14 new objects :)

The source code for `drawOn:` includes a block closure:

```smalltalk
SBECrossMorph >> drawOn: aCanvas
  | topAndBottom |
  aCanvas fillRectangle: self horBar color: self color.
  topAndBottom := self verBar areasOutside: self horBar.
  topAndBottom do: [:each | aCanvas fillRectangle: each color: self color].
```

I think my block closure handling is correct. However, be aware that `Rectangle >> areasOutside:` is a dummy implementation for now; I only implemented it to give me an Array for the closure.

# ST2bash
Check out the Smalltalk-to-Bash compiler generated for me by Claude Opus. Currently it should be able to match all my hand-compiled examples (excluding BlockClosures). Open problems it raises:

- How to represent references to string literals?
