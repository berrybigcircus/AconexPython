import datetime
import pypdf
from pypdf.annotations import Link
import json
import base64 #for downloading signature image files
import os #for deleting the signature files
from PIL import Image #for saving image files
import img2pdf #for converting image files to pdf

FILEPATH = "3-Field/"

class PDFForm:
    def __init__(self, filename):
        self.pageheight = None
        self.reader = None
        self.writer = None
        self.pages = []
        self.filename = filename
        self.loadreaderwriter()

    def loadreaderwriter(self):
        self.reader = pypdf.PdfReader(FILEPATH + self.filename)
        self.writer = pypdf.PdfWriter()
        self.writer.append(self.reader)
        self.pageheight = self.reader.pages[0].mediabox.height

    def reader(self) -> pypdf.PdfReader:
        return self.reader

    def createPages(self, map, linkFunc):
        numpages = len(map)
        self.pages = []

        for p in range(numpages):
            pageMap = map[p]
            pageFields = {}
            pageSignatures = []
            pageLinks = []

            for kFF, vQ in pageMap.items():
                pdfNames = kFF.fieldNames()
                questionVals = vQ.value(kFF.timeSeparate())
                for i, name in enumerate(pdfNames):
                    if questionVals[i]:
                        pageFields[name] = questionVals[i]
                        if kFF.hasLink():
                            kFF.makeUrl(linkFunc(questionVals[i]))
                            pageLinks.append(kFF.link())

                sig = kFF.signature()
                if sig:
                    if sig.hasStamp(): pageSignatures.append(sig) #if form field is signature and signature has a value, get signaturebox



            self.pages.append(PDFPage(pageFields, pageSignatures, pageLinks))

        self.updatepdf()

    def updatepdf(self):
        for i, page in enumerate(self.pages):
            self.writer.update_page_form_field_values(
                self.writer.pages[i],
                page.formfields(),
                auto_regenerate=False,
            )

            for signature in page.signatureBoxes:
                self.writer.pages[i].merge_transformed_page(signature.stamp, signature.stampLocSize)

            for link in page.linkAnnotations:
                self.writer.add_annotation(page_number=i, annotation=link.getAnnotation())

    def createExportedPDF(self, newname):
        with open(FILEPATH + newname, "wb") as output_stream:
            self.writer.write(output_stream)
        print("Absolutely smashed it mate. Done it. Look at this -> %s" % newname)

class PDFPage:
    def __init__(self, fields, signatures, links=None):
        self.__formfields : dict = fields
        self.signatureBoxes = signatures
        self.linkAnnotations = links

    #return in dictionary format
    def formfields(self) -> dict:
        return self.__formfields

class SignatureBox:
    def __init__(self, name, width : int, height : int, xpos : int, ypos : int):
        self.name = name #not needed for anything
        self.boxwidth = width
        self.boxheight = height
        # bottom left(?) corner
        self.xpos = xpos
        self.ypos = ypos
        self.stamp = None
        self.stampLocSize = None
        self.stampPath = None

    def createStamp(self, pageheight : int, pdfpath: str):
        self.stampPath = pdfpath
        self.stamp = pypdf.PdfReader(pdfpath).pages[0]
        stampBox = self.stamp.mediabox
        stampheight = stampBox.height
        stampwidth = stampBox.width
        scaleFactor = min(self.boxheight / stampheight, self.boxwidth / stampwidth)
        self.stampLocSize = (pypdf.Transformation()
                        .scale(scaleFactor, scaleFactor)
                        .translate(tx=self.xpos, ty=pageheight - self.ypos))

    def hasStamp(self) -> bool:
        return self.stamp

    #destructor
    def __del__(self):
        if self.stampPath:
            try:
                os.remove(self.stampPath)
            except FileNotFoundError:
                pass

class LinkAnnotation:
    def __init__(self, name, rect:[float]):
        self.annotation = None
        self.name = name
        self.__rect = rect

    def createLink(self, url:str):
        self.annotation = Link(
            rect = self.__rect,
            url=url
        )
        self.annotation.flags = 4

    def getAnnotation(self) -> Link:
        return self.annotation

class FormField: #for text fields and dates
    def __init__(self, name : str):
        self._name : str = name

    def fieldNames(self) -> list[str]:
        return [self._name]

    def signature(self) -> SignatureBox:
        return None

    def hasLink(self) -> bool:
        return False

    def timeSeparate(self) -> bool:
        return False

class FormCheckbox(FormField):
    def __init__(self, names :list[str]):
        self._name = names

    #Override
    def fieldNames(self) -> list[str]:
        return self._name

class FormLink(FormField):
    def __init__(self, name: str, link):
        super().__init__(name)
        self.__link = link

    #Override
    def hasLink(self) -> bool:
        return True

    def link(self) -> LinkAnnotation:
        return self.__link

    def makeUrl(self, url: str):
        if url: #if valid url was created from aconex search of doc register
            self.__link.createLink(url)

class FormSignature(FormField):
    def __init__(self, signature, name=None, date=None,  time=None):
        self._name : str = name #name of field asking for person's name
        self.__date : str = date #date or date+time
        self.__time : str = time
        self.__signature : SignatureBox = signature

    #Override
    def fieldNames(self) -> list[str]:
        nameconcat = []
        for field in [self._name, self.__date, self.__time]:
            if field:
                nameconcat.append(field)

        return nameconcat

    #if time is a separate field or is joined into the date
    def timeSeparate(self) -> bool:
        return (self.__time)

    #override
    def signature(self) -> SignatureBox:
        return self.__signature

    def stampSignature(self, pdfpath : str):
        self.signature().createStamp(self.pageheight, pdfpath)

class Question: #for text questions
    def __init__(self, questionnum):
        self.questionnum = questionnum
        self.description = None
        self._response = None

    def readJsonVals(self, jsonAll: list[dict]):
        index = self.questionnum -1 #list will start at 0 not question 1
        self.description = jsonAll[index]["description"]
        self.response(jsonAll[index]["response"]["value"])

    #setter
    def response(self, r):
        self._response = r

    #getter
    def value(self, separateTime=False) -> list[str]:
        return [self._response]

    def hasValue(self) -> bool:
        return any(self.value())

class DateQuestion (Question):
    def response(self, r):
        self._response = convertDate(r)

class ItemQuestion (Question):
    def __init__(self, itemnum):
        self.response(itemnum)

    # override
    def readJsonVals(self, jsonAll: list[dict]):
        pass

class CheckboxQuestion (Question):
    def __init__(self, questionnum, valueIfTrue="Yes", valueIfFalse = "No"):
        super().__init__(questionnum)
        self.valueIfTrue = valueIfTrue
        self.valueIfFalse = valueIfFalse

    #Override getter
    def value(self, separateTime=False) -> list[str]:
        if self._response == self.valueIfTrue:
            return ["/Yes", "/Off"]
        else:
            return ["/Off", "/Yes"]

class SignatureQuestion (Question):
    def __init__(self, questionnum):
        super().__init__(questionnum)
        self.name = None
        self.date = None
        self.time = None
        self.image = None

    def response(self, r):
        self._response = json.loads(r)
        self.name = self._response['name']

        if self.name != "": #check there is a signature value
            self.date, self.time = convertDateTime(self._response["respondedAt"])
            self.image = self._response['signature']

        else: self.name = None

    def saveSignatureFile(self) -> str:
        return loadSignature(self.image, str(self.questionnum))

    #getter
    def value(self, separateTime=True) -> list[str]:
        if separateTime or not self.date:
            return [self.name, self.date, self.time]
        else:
            return [self.name, self.date + " " + self.time]


class Questions:
    def __init__(self, questions):
        self.__questions: list[Question] = questions
        self.join = (len(self.__questions) > 1) #if there is multiple questions for one pdf field, they need to be joined together

    def getQuestions(self) -> list[Question]:
        return self.__questions

    def value(self, separateTime=False) -> list[str]:
        if self.join:
            return ["\n".join([val for q in self.__questions for val in q.value(separateTime)])]
        else:
            return [val for q in self.__questions for val in q.value(separateTime)]

class FieldTemplate:
    def __init__(self, rawJson : dict):
        self.checklistnumber = rawJson['number']
        # take the questions out of the groups, store in one dictionary
        self.jsonAllItems : list[dict] = [itemArr for g in rawJson['groups'] for itemArr in g['items']] #add items in group
        self.jsonAllItems.extend([itemArr for itemArr in rawJson['items']])

class ChecklistPDFMap:
    def __init__(self, rawJson, filename):
        self.map : list[dict] = []
        self.template = FieldTemplate(rawJson)
        self.pdfform = PDFForm(filename)
        self.hyperlinkcreator = None
        print("Exporting the Field checklist into pdf %s ..." % filename)

    def getQuestionValues(self):
        for pageDict in self.map:
            for formKey, qsVal in pageDict.items():
                for question in qsVal.getQuestions():
                    question.readJsonVals(self.template.jsonAllItems)
                    if type(question) == SignatureQuestion and question.hasValue(): #if a non-blank signature
                        pdfSigpath = question.saveSignatureFile()
                        formKey.signature().createStamp(self.pdfform.pageheight, pdfSigpath)

    def hyperlinkFunction(self, createUrl):
        self.hyperlinkcreator = createUrl

    def export(self, templateTitle: str, projectname: str):
        self.createMap()

        print("Creating file...")
        newname = projectname + " - " + templateTitle + " - " + str(self.template.checklistnumber) + ".pdf"
        self.pdfform.createExportedPDF(newname)

    #Abstract
    def createMap(self):
        pass

class HotworksMap(ChecklistPDFMap):
    def createMap(self):
        fws = SignatureBox("FireWatcher", width=150, height=15, xpos=270, ypos=200)
        acs = SignatureBox("Acceptance", width=160, height=40, xpos=390, ypos=340)
        cls = SignatureBox("Clearance", width=160, height=40, xpos=390, ypos=620)
        ves = SignatureBox("Verification", width=160, height=40, xpos=390, ypos=765)
        iq = ItemQuestion(self.template.checklistnumber)
        ramsLink = LinkAnnotation("LinktoRams", [130, 841-690, 560, 841-640]) #position where link to rams will be on the page [xLL, yLL, xUR, yUR]

        self.map = [
            { #page 1
                FormField("ItemNum"): Questions([iq]),
                FormField("Date"): Questions([DateQuestion(6)]),
                FormField("From"): Questions([Question(7)]),
                FormField("To"): Questions([Question(8)]),
                FormField("WorkLocDesc"): Questions([Question(4), Question(3)]),
                FormLink("RAMSRef", ramsLink): Questions([Question(5)])
            },
            { #page 2
                FormCheckbox(["FireWatchYes", "FireWatchNo"]): Questions([CheckboxQuestion(21)]),
                FormSignature(name="FireWatcherName", date="FireWatchDateTime", signature=fws): Questions([SignatureQuestion(22)]),
                FormSignature(name="AcceptanceName", date="AcceptanceSigDate", signature=acs, time="AcceptanceSigTime"): Questions([SignatureQuestion(23)]),
                FormField("Company"): Questions([Question(1)]),
                FormSignature(name="ClearanceName",date="ClearanceDate", signature=cls, time="ClearanceTime"): Questions([SignatureQuestion(25)]),
                FormSignature(name="VerificationName",date="VerificationDate", signature=ves,time="VerificationTime"): Questions([SignatureQuestion(28)])
            }
        ]

        self.getQuestionValues()

        self.pdfform.createPages(self.map, self.hyperlinkcreator)

class DigMap(ChecklistPDFMap):
    def createMap(self):
        aus = SignatureBox("Authorisation", width=120, height=30, xpos=180, ypos=440)
        sus = SignatureBox("Supervisor", width=120, height=35, xpos=180, ypos=560)
        mcs = SignatureBox("MachineController", width=120, height=30, xpos=180, ypos=675)
        ebs = SignatureBox("Banksman", width=120, height=30, xpos=180, ypos=150)
        cls = SignatureBox("Clearance", width=120, height=30, xpos=180, ypos=270)
        ves = SignatureBox("Verification", width=120, height=30, xpos=180, ypos=330)
        iq = ItemQuestion(self.template.checklistnumber)
        ramsLink = LinkAnnotation("LinktoRams", [140, 792-355, 536, 792-325]) #position where link to rams will be on the page

        self.map = [
            {  # page 1
                FormField("ItemNum"): Questions([iq]),
                FormField("From"): Questions([DateQuestion(7),Question(9)]),
                FormField("To"): Questions([DateQuestion(8), Question(10)]),
                FormField("WorkLocDesc"): Questions([Question(4), Question(3)]),
                FormLink("RAMSRef", ramsLink): Questions([Question(6)]),
                FormField("Company"): Questions([Question(1)]),
                FormSignature(name="AuthorisationName",date="AuthorisationDate", signature=aus, time="AuthorisationTime"): Questions([SignatureQuestion(38)]),
                FormSignature(name="AcceptanceName", date="AcceptanceDate", signature=sus, time="AcceptanceTime"): Questions([SignatureQuestion(35)]),
                FormSignature(name="MControllerName", date="MControllerDate", signature=mcs, time="MControllerTime"): Questions([SignatureQuestion(36)]),
            },
            {  # page 2
                FormSignature(name="BanksmanName", date="BanksmanDate", signature=ebs, time="BanksmanTime"): Questions([SignatureQuestion(37)]),
                FormSignature(name="ClearanceName", date="ClearanceDate", signature=cls, time="ClearanceTime"): Questions([SignatureQuestion(39)]),
                FormSignature(name="VerificationName", date="VerificationDate", signature=ves, time="VerificationTime"): Questions([SignatureQuestion(40)])
            }
        ]

        self.getQuestionValues()

        self.pdfform.createPages(self.map, self.hyperlinkcreator)


def convertDate(dateResponseRaw : str) -> str:
    date = datetime.datetime.strptime(dateResponseRaw, "%Y-%m-%d")
    return datetime.datetime.strftime(date, "%a, %d %b %Y")

def convertDateTime(dateResponseRaw : str) -> (str, str):
    dateAndTime = datetime.datetime.strptime(dateResponseRaw, "%Y-%m-%dT%H:%M:%S.%fZ")
    formatted = datetime.datetime.strftime(dateAndTime, "%a, %d %b %Y && %I:%M%p")
    return formatted.split(" && ")

def getJSONResponseVal(jsonList, desc) -> str:
    return [js['response']['value'] for js in jsonList if js['description'] == desc][0]

def loadSignature(signatureData, filename) -> str:
    signatureImagedata = signatureData.split(',')

    extstart = signatureImagedata[0].index("/") + 1
    extend = signatureImagedata[0].index(";", extstart)
    fileext = '.' + signatureImagedata[0][extstart:extend]

    fullpath = FILEPATH + "signatures/" + filename + fileext
    with open(fullpath, 'wb') as f:
        f.write(base64.b64decode(signatureImagedata[1]))
        f.close()

    return image_to_pdf(fullpath, fileext)

def image_to_pdf(imagePath: str, imageExt : str) -> str:
    img = Image.open(imagePath)
    pdf_bytes = img2pdf.convert(img.filename)
    pdfPath = imagePath.replace(imageExt,'.pdf')
    file = open(pdfPath, "wb")
    file.write(pdf_bytes)
    img.close()
    file.close()
    os.remove(imagePath)
    return pdfPath

