# Example Mermaid Diagrams

This folder contains sample Mermaid diagram files that you can open in the application to test various diagram types.

## Files

- **sample.mmd** - Simple flowchart with styling
- **sequence.mmd** - Sequence diagram showing the app's architecture

## Try These Diagram Types

### Flowchart
```mermaid
graph LR
    A[Square] --> B(Rounded)
    B --> C{Decision}
    C -->|Yes| D[Result 1]
    C -->|No| E[Result 2]
```

### Class Diagram
```mermaid
classDiagram
    Animal <|-- Duck
    Animal <|-- Fish
    Animal : +int age
    Animal : +String gender
    Animal: +isMammal()
    class Duck{
        +String beakColor
        +swim()
    }
    class Fish{
        -int sizeInFeet
        -canEat()
    }
```

### State Diagram
```mermaid
stateDiagram-v2
    [*] --> Still
    Still --> [*]
    Still --> Moving
    Moving --> Still
    Moving --> Crash
    Crash --> [*]
```

### Gantt Chart
```mermaid
gantt
    title Project Timeline
    dateFormat YYYY-MM-DD
    section Phase 1
    Design           :a1, 2026-01-01, 30d
    Development      :a2, after a1, 45d
    section Phase 2
    Testing          :a3, after a2, 20d
    Deployment       :a4, after a3, 10d
```

### Pie Chart
```mermaid
pie
    title Programming Languages
    "C#" : 45
    "JavaScript" : 25
    "Python" : 20
    "Other" : 10
```

## Tips

1. Copy any of the examples above into the app's editor
2. The preview will update automatically after you stop typing
3. Experiment with different themes (dark, forest, neutral)
4. Try different scale factors for higher quality exports
5. Use transparent background for diagrams you'll overlay on other content
