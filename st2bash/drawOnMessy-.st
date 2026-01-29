drawOnMessy: aCanvas
    | topAndBottom1 topAndBottom2 topAndBottoms |
 	topAndBottom1 := Array with: (self bounds) with: (Rectangle origin: 0@0 corner: 100@100).
   topAndBottom2 := Array with: (self bounds) with: (Rectangle origin: 100@100 corner: 200@200).
   topAndBottoms := Array with: topAndBottom1 with: topAndBottom2.
 	topAndBottoms do: [:eachArray |
        | myTemp |
        myTemp := 3.
        eachArray do: [:each | aCanvas fillRectangle: each color: self color].
    ].