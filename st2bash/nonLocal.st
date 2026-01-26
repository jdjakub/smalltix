containsInstanceOf: aClass
    self do: [ :elem | (elem isMemberOf: aClass) ifTrue: [^true] ].
    ^false