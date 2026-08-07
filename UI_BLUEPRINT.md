UI BLUEPRINT



Project: DICOMStudio



Version: 1.0



Status: Approved



1\. Design Vision



The user interface shall provide a modern, clean, and efficient workspace optimized for medical image visualization.



The interface should feel familiar to users of professional desktop software while remaining approachable for students and researchers.



The design must prioritize:



Clarity

Speed

Minimal distractions

Efficient workflows

Consistency

Accessibility



Every visual element must serve a functional purpose.



2\. Design Principles



The UI shall follow these principles:



Minimalist

Functional

Consistent

Responsive

Predictable

Keyboard-friendly

Mouse-friendly

High-DPI ready



Avoid unnecessary visual effects.



Avoid clutter.



Avoid hidden functionality.



3\. Application Layout



The application uses a three-panel workspace with persistent top and bottom bars.



+----------------------------------------------------------------------------------+

| Menu Bar                                                                         |

+----------------------------------------------------------------------------------+

| Toolbar                                                                          |

+----------------------------------------------------------------------------------+

| Study Explorer |                  Image Viewer                  | Metadata Panel |

|                |                                                |                |

|                |                                                |                |

|                |                                                |                |

|                |                                                |                |

|                |                                                |                |

+----------------------------------------------------------------------------------+

| Status Bar                                                                       |

+----------------------------------------------------------------------------------+



This layout provides immediate access to navigation, visualization, and metadata without switching screens.



4\. Main Window Structure



The main window consists of:



Menu Bar



Provides access to application-wide actions.



Menus:



File

View

Tools

Window

Help

Toolbar



Contains frequently used tools.



Examples:



Open Folder

Open Files

Fit to Window

Zoom In

Zoom Out

Reset View

Window/Level

Measure

Screenshot

Settings



Toolbar icons should include tooltips and keyboard shortcuts where applicable.



Left Panel — Study Explorer



Displays the hierarchical structure of loaded studies.



Hierarchy:



Patient

&#x20;└── Study

&#x20;     └── Series

&#x20;          └── Images



Responsibilities:



Browse studies

Browse series

Show thumbnails

Display modality

Display image count



The panel should support expand/collapse behavior and fast navigation.



Center Panel — Image Viewer



This is the primary workspace.



Responsibilities:



Display medical images

Zoom

Pan

Scroll slices

Overlay measurements

Display orientation markers

Display pixel values (future overlay)



The image should always remain the visual focus.



Right Panel — Metadata Panel



Displays DICOM metadata.



Features:



Search

Expand/Collapse groups

Copy tag

Copy value

Filter tags



Metadata should be grouped logically (Patient, Study, Series, Image, Acquisition, etc.) for readability.



Status Bar



Displays contextual information.



Examples:



Loaded study

Slice number

Zoom level

Window Width

Window Level

Pixel coordinates

Pixel value

Application status



Information should update dynamically as the user interacts with the image.



5\. Navigation Workflow



The primary workflow should be intuitive:



Open Folder

&#x20;     ↓

Study Explorer

&#x20;     ↓

Select Study

&#x20;     ↓

Select Series

&#x20;     ↓

Display Image

&#x20;     ↓

Navigate

&#x20;     ↓

Inspect Metadata

&#x20;     ↓

Measure

&#x20;     ↓

Export



No unnecessary modal dialogs should interrupt this workflow.



6\. Viewer Behavior



The image viewer should support:



Mouse wheel → Scroll slices

Left mouse drag → Pan (when Pan tool is active)

Right mouse drag → Window/Level adjustment (common in radiology viewers)

Double-click → Fit to window or reset zoom (configurable)

Keyboard shortcuts for common actions



Interactions should feel smooth and responsive.



7\. Dockable Panels



The following panels should be dockable:



Study Explorer

Metadata Panel



Users should be able to:



Show/Hide

Resize

Dock

Undock

Restore default layout



Panel layout should persist between sessions.



8\. Color System



Default theme: Dark Mode



Suggested palette:



Background: Dark charcoal

Viewer background: Near black

Primary accent: Blue

Success: Green

Warning: Amber

Error: Red

Text: Light gray / white



Accent colors should be used sparingly to highlight interactive elements and selected items.



9\. Typography



Primary font:



Segoe UI (Windows-native)

Fallback: Inter or Noto Sans



Guidelines:



Clear hierarchy

Readable sizes

Avoid decorative fonts

Consistent spacing

10\. Iconography



Use a single icon set throughout the application (e.g., Fluent UI or Material Symbols).



Icons should be:



Simple

Consistent

High contrast

Scalable



Every icon should have a tooltip.



Avoid mixing multiple icon styles.



11\. Spacing \& Layout



Adopt an 8-pixel spacing system.



Recommendations:



Uniform margins

Consistent padding

Balanced whitespace

Aligned controls



A clean layout improves usability and maintainability.



12\. Keyboard Shortcuts



Core shortcuts:



Ctrl + O → Open Folder

Ctrl + Shift + O → Open Files

Ctrl + S → Export Image

Ctrl + , → Settings

Ctrl + 0 → Fit to Window

\+ / - → Zoom In / Out

Delete → Remove selected measurement

F11 → Fullscreen



Shortcuts should be configurable in the future.



13\. Responsive Behavior



The layout should adapt gracefully to different window sizes.



Rules:



Viewer has the highest resize priority.

Side panels shrink before the viewer.

Minimum widths prevent unusable panels.

High-DPI scaling must be supported.

14\. Accessibility



The interface should provide:



High-contrast theme support (future)

Keyboard navigation

Visible focus indicators

Scalable fonts where appropriate

Descriptive tooltips



Accessibility should be considered from the beginning rather than added later.



15\. Visual Feedback



Provide immediate feedback for user actions.



Examples:



Loading indicator while scanning studies.

Progress bar for long-running operations.

Hover effects on interactive controls.

Disabled appearance for unavailable actions.

Non-blocking notifications for completed tasks.



Avoid unnecessary animations.



16\. Empty States



Design informative empty states instead of blank screens.



Examples:



No Study Loaded: Prompt the user to open a folder.

No Series Selected: Explain how to select a series.

No Metadata Available: Display a clear message rather than an empty panel.



These states should guide the user without being intrusive.



17\. Error Presentation



Errors should be presented clearly and professionally.



Principles:



Explain what happened.

Suggest the next action when possible.

Avoid exposing stack traces in user dialogs.

Log technical details separately.



Critical errors should never freeze the application.



18\. Future UI Extensions



The layout should accommodate future features without major redesign.



Reserved areas include:



MPR workspace

3D viewer

AI assistant panel

PACS browser

Plugin panels

Multi-monitor workflows



The existing layout should scale naturally as these capabilities are introduced.



19\. UI Consistency Rules



Every screen and component should follow the same design language:



Consistent spacing

Consistent typography

Consistent icons

Consistent button styles

Consistent dialog behavior

Consistent terminology



Users should never have to relearn interactions in different parts of the application.



20\. Definition of a Professional UI



The interface is considered complete when it:



Feels responsive.

Looks modern without unnecessary decoration.

Makes common tasks easy.

Keeps the medical image as the primary focus.

Minimizes clicks for frequent actions.

Maintains consistency across the application.

Scales well to future features.

Provides a polished desktop experience comparable to professional imaging software.

