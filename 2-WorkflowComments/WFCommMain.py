from OAuth import UK1setup, EAsetup
from OAuth.config import init

import WorkflowComments

init(UK1setup.bearer, UK1setup.env, debug=[])
WorkflowComments.main(inputUseTextFile=input("Generate from docsList.txt? (Y/N): ").lower())



#WFS Wisbech
# init(UK1setup.bearer, UK1setup.env, debug=["DfE Wisbech Free School","268454433", "FS1018"])
# WorkflowComments.main(inputUseTextFile="n")

#FS1018 DfE Wisbech (268454433)

