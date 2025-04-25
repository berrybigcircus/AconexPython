from OAuth import UK1setup
from OAuth.APIcommon import projectSelection, Project

import WorkflowComments

#WorkflowComments.main(UK1setup.bearer,'https://uk1.aconex.co.uk', projectSelection(),
# inputUseTextFile=input("Generate from docsList.txt? (Y/N): ").lower())  #pass in environment, for urls)

#WFS Wisbech
WorkflowComments.main(UK1setup.bearer,'https://uk1.aconex.co.uk',
                      Project('FS1018 DfE Wisbech Free School', '268454433', "WFS"),
                      inputUseTextFile="n")  #pass in environment, for urls)
