
from OAuth import EAsetup #perform EA auth
import newUser
from OAuth.ProjectClasses import projectSelection

newUser.main(passedBearer = EAsetup.bearer, env=EAsetup.env, project=projectSelection(debug=True))  #pass in environment, for urls
#newUser.updateTracker("HB Test", userData)
