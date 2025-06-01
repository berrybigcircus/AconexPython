from OAuth import EAsetup, UK1setup
from OAuth.config import init
from OAuth.ProjectClasses import Project, projectSelection

from RFIs import RFITracker

#EA test
#init(EAsetup.bearer, EAsetup.env, project=projectSelection(debug=True))

#CDC
init(UK1setup.bearer, UK1setup.env, project=Project("NUHT Community Diagnostics Centre", "268456728", "CDC"))

RFITracker.main()

#RFITracker.main(passedBearer = UK1setup.bearer, env=UK1setup.env, project=projectSelection())