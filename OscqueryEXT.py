import json
import struct
from TDStoreTools import StorageManager
TDJ = op.TDModules.mod.TDJSON


class Oscquery:
	"""
	Oscquery description
	"""
	def __init__(self, ownerComp):
		# The component to which this extension is attached
		self.ownerComp = ownerComp

	def clearStorage(self):
		self.ownerComp.unstore("/*")

	def GetAllAddresses(self):
		storage = self.ownerComp.storage
		oscAddresses = []

		for i, (key, value) in enumerate(storage.items()):
			oscAddresses.append(key)

		return oscAddresses


	def ReceiveOsc (self, address, args):
		stored = self.ownerComp.fetch(address)
		parameter = stored["par"]
		parStyle = parameter.style

		if not self.writeIsAllowed(parameter):
			parName = parameter.name
			print ("OSCQuery: Setting parameter " + parName + " which is read only or has an active expression or export is prevented.")
			return

		if parStyle in ["XY", "XYZ", "UV", "UVW", "WH"]:
			for i, p in enumerate(parameter.tuplet):
				p.val = args[i]

		elif parStyle in ["RGB", "RGBA"]:
			value = args[0]
			color = []

			if isinstance(value, float):
				color = args

			else:
				try:
					value = struct.unpack('<BBBB', value)
				except (UnicodeDecodeError, AttributeError):
					pass

				if isinstance(value, tuple):
					color.append(value[0] / 255)
					color.append(value[1] / 255)
					color.append(value[2] / 255)
					color.append(value[3] / 255)

			for i, p in enumerate(parameter.tuplet):
				p.val = color[i]
			
		elif parStyle == "Pulse":
			parameter.pulse()

		elif parStyle == "Menu":
			value = args[0]
			labels = parameter.menuLabels
			values = parameter.menuNames
			index = labels.index(value)
			key = values[index]
			parameter.val = key

		else:
			parameter.val = args[0]


	def GetJson(self, uri="/", pars={}):
		if (uri == "/"):
			result = self.getFullJson(pars)
			jsonText = TDJ.jsonToText(result)
			return jsonText
		
		else:
			result = self.getFullJson(pars)
			uriSegments = uri.split("/")
			uriSegments.pop(0)
			segment = self.getSegment(result, uriSegments)
			jsonText = TDJ.jsonToText(segment)
			return jsonText


	def getSegment(self, segment, uriSegments):
		if (len(uriSegments) <= 0):
			return segment
		else:
			segmentName = uriSegments.pop(0)
			segment = segment["CONTENTS"][segmentName]
			return self.getSegment(segment, uriSegments)


	def getFullJson(self, pars={}):
		hostinfoRequested = "HOST_INFO" in pars

		if hostinfoRequested:
			return self.getHostinfoJson()
		
		self.clearStorage() # clear storage, to rebuild on each request
		
		result = {
			"DESCRIPTION": str(self.ownerComp.par.Name), 
			"CONTENTS": { }
		}

		for i in range(1,11):
			compPath = getattr(self.ownerComp.par, "Comp" + str(i))
			container = self.ownerComp.op(compPath)

			if container:
				oscPrefix = self.getPrefix(container, i)
				includePagesInPath = getattr(self.ownerComp.par, "Includepagesinoscpath" + str(i))
				# print(compPath, oscPrefix, includePagesInPath)

				pages = container.customPages
				compResult = {}
				contents = {}

				for page in pages:
					if (page.isCustom):
						parameters = page.pars
						pageName = page.name
						
						for parameter in parameters:
							isSingleParameter = (parameter.name == parameter.tupletName)

							if (isSingleParameter or (not isSingleParameter and parameter.vecIndex == 0) ):
								parameterName = parameter.tupletName
								
								if (includePagesInPath):
									oscAddress = "/" + oscPrefix + "/" + pageName + "/" + parameterName
								else:
									oscAddress = "/" + oscPrefix + "/" + parameterName

								par = {}
								par["TYPE"] = self.getType(parameter)
								par["DESCRIPTION"] = parameterName
								par["FULL_PATH"] = oscAddress

								if (par["TYPE"] != "N"):	# all except pulse parameter
									par["VALUE"] = self.getValue(parameter)

								if (par["TYPE"] not in ["s", "r", "N"] or
									parameter.style == "Menu"):
									par["RANGE"] = self.getRange(parameter)

								par["ACCESS"] = self.getAccess(parameter)

								contents[parameterName] = par

								storageItem = { 
									"par": parameter,
									"type": par["TYPE"]
								}

								self.ownerComp.store(oscAddress, storageItem)
								print(oscAddress)
							
						if (includePagesInPath):
							compResult[pageName] = {}
							compResult[pageName]["CONTENTS"] = contents
							contents = {}
				

				if (includePagesInPath):
					result["CONTENTS"][oscPrefix] = {}
					result["CONTENTS"][oscPrefix]["CONTENTS"] = compResult
				else:
					result["CONTENTS"][oscPrefix] = {}
					result["CONTENTS"][oscPrefix]["CONTENTS"] = contents

		return result


	def getValue(self, parameter):

		if (parameter.style in ["XY", "UV", "WH"]):
			return [parameter.tuplet[0].eval(), parameter.tuplet[1].eval()]

		if (parameter.style in ["XYZ", "UVW"]):
			return [parameter.tuplet[0].eval(), parameter.tuplet[1].eval(), parameter.tuplet[2].eval()]

		if (parameter.style in ["RGB", "RGBA"]):
			r = self.getHex(parameter.tuplet[0].eval())
			g = self.getHex(parameter.tuplet[1].eval())
			b = self.getHex(parameter.tuplet[2].eval())
			a = "ff" if parameter.style == "RGB" else self.getHex(parameter.tuplet[3].eval())
			return ["#" + r + g + b + a]

		if (parameter.style == "Menu"):
			curValue = parameter.val
			menuLabels = parameter.menuLabels
			menuNames = parameter.menuNames
			
			index = menuNames.index(curValue)
			key = menuLabels[index]
			
			return [key]

		if (parameter.style in ["CHOP", "COMP", "DAT", "SOP", "MAT", "TOP"]):
			return [parameter.val]
		else:
			return [parameter.eval()]


	def getHex(self, f):
		v = hex(int(f * 255))[2:]
		v = v if len(v) == 2 else "0" + str(v)
		return v


	def getRange(self, parameter):

		if (parameter.style == "Toggle"):
			return [{ "MAX": 1, "MIN": 0 }]

		if (parameter.style in ["XY", "UV", "WH", "XYZ", "UVW"]):
			result = []

			for charIndex in range(len(parameter.style)):
				newRange = { "MAX": parameter.tuplet[charIndex].normMax, "MIN": parameter.tuplet[charIndex].normMin }
				result.append(newRange)

			return result

		if (parameter.style == "Menu"):
			return [{ "VALS": parameter.menuLabels }]

		return [{ "MAX": parameter.normMax, "MIN": parameter.normMin }]


	def getType (self, parameter):
		t = parameter.style

		if (t == "Float"):
			return "f"
		elif (t == "Int"):
			return "i"
		elif (t in ["Str", "File", "Folder", "CHOP", "COMP", "DAT", "SOP", "MAT", "TOP", "Menu", "StrMenu"]):
			return "s"
		elif (t == "Toggle"):
			return "T"
		elif (t in ["RGB", "RGBA"]):
			return "r"
		elif (t in ["XY", "UV", "WH"]):
			return "ff"
		elif (t in ["XYZ", "UVW"]):
			return "fff"
		elif (t == "Pulse"):
			return "N"

		return "f"


	def getAccess (self, parameter):
		if (parameter.mode == ParMode.CONSTANT and parameter.readOnly != 1):
			return 3	# read and write access
		else:
			return 1	# read-only access
	

	def getPrefix(self, container, i):
		if not container:
			return ""
			
		customPrefix = str(getattr(self.ownerComp.par, "Oscprefix" + str(i)))

		if not customPrefix:
				return str(container.name)
		else:
			return customPrefix


	def writeIsAllowed(self, parameter):
		for p in parameter.tuplet:
			if (p.mode != ParMode.CONSTANT or p.readOnly == 1):
				return False

		return True

	def getHostinfoJson(self):
		return {
				"NAME": str(self.ownerComp.par.Name),
				"OSC_PORT": int(self.ownerComp.par.Port),
				"OSC_TRANSPORT": "UDP",
				"EXTENSIONS": {
					"PATH_REMOVED": False,
					"CRITICAL": False,
					"VALUE": True,
					"PATH_CHANGED": False,
					"PATH_RENAMED": False,
					"CLIPMODE": False,
					"LISTEN": False,
					"RANGE": True,
					"HTML": False,
					"PATH_ADDED": False,
					"UNIT": False,
					"ACCESS": True,
					"IGNORE": False,
					"TAGS": False
				}
		}