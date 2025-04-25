from OAuth import EAsetup, UK1setup
from OAuth.APIcommon import projectSelection
from RFIs import RFITracker

RFITracker.main(passedBearer = EAsetup.bearer, env=EAsetup.env, project=projectSelection(debug=True))  #pass in environment, for urls)

#RFITracker.main(passedBearer = UK1setup.bearer, env=UK1setup.env, project=projectSelection())