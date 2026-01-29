drawOn: aCanvas
  (Array with: self horBar with: self verBar) do: [ :rect |
    aCanvas fillRectangle: rect color: self color.
    ]