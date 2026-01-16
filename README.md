Works on Windows WSL Ubuntu, because colons in message names get mangled to dash: e.g. `doSomethingWith:and:andAlso:` becomes `doSomethingWith-and-andAlso-`. Requires `bc` for bash arithmetic.

Example: `SBECrossMorph` from Squeak By Example 6.0.

```bash
sudo apt install bc
aRect=$(./send aCross horBar)
```

Inspect `$aRect` in your file browser...

It should be among 4 new objects (directories) created.

Two are its points, one was a temporary point that ought to be garbage collected. (I suggest "Move to Recycle Bin"...)

# ST2bash
Check out the Smalltalk-to-Bash compiler generated for me by Claude Opus. Currently it should be able to match all my hand-compiled examples. Open problems it raises:

- How to represent references to string literals?
- How to do blocks and block closures? (As I was warned by a Smalltalker in my June 2025 lightning talk: I'll have to face this eventually, and that's where all the fun begins...!)
