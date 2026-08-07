MILESTONE PROMPT FRAMEWORK

Purpose



This document defines the standard prompt structure used for every development milestone in the DICOMStudio project.



The objective is to provide the AI coding agent with enough context to implement the requested feature while keeping prompts concise, focused, and consistent.



Every implementation request must follow this structure.



Prompt Structure



Every milestone prompt consists of 7 sections.



1\. Current Context



Tell the AI where the project currently stands.



Example:



You are contributing to the DICOMStudio project.



The repository already follows the approved architecture and coding standards.



Review the current codebase before making any modifications.



Implement only the requested milestone.



Do not modify unrelated modules.

2\. Current Milestone



Specify the milestone.



Example:



Milestone



Image Viewer

3\. Objective



Describe the purpose in one paragraph.



Example:



Build the image viewer capable of displaying grayscale DICOM images while maintaining a responsive desktop experience.

4\. Requirements



Only list the functionality required for this milestone.



Example:



Requirements



• Display image

• Zoom

• Pan

• Fit to Window

• Slice Navigation

• Reset View

5\. Constraints



Clearly state what must not be implemented.



Example:



Do NOT implement



Measurements



Annotations



Metadata Panel



Image Export



Plugins



AI Features

6\. Definition of Done



Tell the AI when the milestone is considered complete.



Example:



Done when



Viewer displays DICOM images correctly.



Zoom and Pan work smoothly.



No UI freezing occurs.



All tests pass.



No linting errors.



No type-checking errors.

7\. Final Instruction



Always finish with one instruction.



Example:



Follow the project architecture, coding standards, UI blueprint, and AI development rules.



Generate production-ready code only.

General Rules



Every milestone prompt must satisfy the following:



Focus on a single milestone.

Never request multiple unrelated features.

Assume previous milestones are already complete.

Do not repeat the full project documentation.

Keep prompts concise.

Reference the existing project standards instead of rewriting them.

Example Prompt

You are contributing to the DICOMStudio project.



Review the existing repository before making changes.



Milestone



Image Viewer



Objective



Implement the image viewer.



Requirements



\- Display grayscale DICOM images

\- Zoom

\- Pan

\- Fit to Window

\- Slice navigation

\- Reset View



Do NOT implement



Measurements



Export



Metadata



Plugins



Done when



Viewer is fully functional.



No UI freezes.



Tests pass.



Follow the existing architecture and coding standards.



Generate production-ready code only.

Milestone Checklist



Before sending any prompt to the AI, verify:



Is the milestone clearly defined?

Does it have one objective?

Are the requirements specific?

Are the constraints listed?

Is the completion criteria clear?

Does it reference the existing project standards?



If all answers are Yes, the prompt is ready.

