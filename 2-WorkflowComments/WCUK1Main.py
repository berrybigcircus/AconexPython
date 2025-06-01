from OAuth import UK1setup, EAsetup
from OAuth.config import init
from OAuth.ProjectClasses import Project, projectSelection

import WorkflowComments

#init(UK1setup.bearer, UK1setup.env, projectSelection())
#WorkflowComments.main(inputUseTextFile=input("Generate from docsList.txt? (Y/N): ").lower())

#WFS Wisbech
init(UK1setup.bearer, UK1setup.env, Project('FS1018 DfE Wisbech Free School', '268454433', "WFS"))
WorkflowComments.main(inputUseTextFile="n")


