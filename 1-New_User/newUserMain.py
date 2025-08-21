import csv

from OAuth import UK1setup #perform auth
from OAuth.config import init
import newUser


# init(UK1setup.bearer, UK1setup.env, debug=["NUHT CDC", "268456728", "CDC"])

init(UK1setup.bearer, UK1setup.env, debug=[])
newUser.main()

#newUser.updateTracker()

#Create project directory xlsx (WIP)
# init(UK1setup.bearer, UK1setup.env, debug=["Leicester Endoscopy", "268455655", "LEU"])
# newUser.projectDirectory()

