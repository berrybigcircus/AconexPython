from OAuth import UK1setup
from OAuth.ProjectClasses import Project, projectSelection

import WorkflowComments

#WorkflowComments.main(UK1setup.bearer,'https://uk1.aconex.co.uk', projectSelection())  #pass in environment, for urls)

#LEU Lendo
WorkflowComments.main(UK1setup.bearer,'https://uk1.aconex.co.uk', Project('Leicester New Endoscopy Unit', '268455655', "LEU"))  #pass in environment, for urls)
