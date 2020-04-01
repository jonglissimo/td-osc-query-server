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
		compPath = stored["comp"]
		container = self.ownerComp.op(compPath)
		parName = stored["par"]
		parStyle = stored["style"]
		parFirstTupletName = stored["firstTupletName"]
		parameter = getattr(container.par, parFirstTupletName)

		if (not self.writeIsAllowed(parameter)):
			print ("OSCQuery: Setting parameter " + parName + " which is read only or has an active expression or export is prevented.")
			return

		if (parStyle in ["XY", "XYZ", "UV", "UVW", "WH"]):
			parameter = getattr(container.par, parFirstTupletName)

			for i, p in enumerate(parameter.tuplet):
				setattr(container.par, p.name, args[i])

		elif (parStyle == "RGB" or
			parStyle == "RGBA"):
			value = args[0]

			if (isinstance(value, float)):
				r = args[0]
				g = args[1]
				b = args[2]
				a = args[3]

			else:
				try:
					value = struct.unpack('<BBBB', value)
				except (UnicodeDecodeError, AttributeError):
					pass

				if isinstance(value, tuple):
					r = value[0] / 255
					g = value[1] / 255
					b = value[2] / 255
					a = value[3] / 255

			setattr(container.par, parName + "r", r)
			setattr(container.par, parName + "g", g)
			setattr(container.par, parName + "b", b)
			
			if (parStyle == "RGBA"):
				setattr(container.par, parName + "a", a)

		elif (parStyle == "Pulse"):
			pulseParameter = getattr(container.par, parName)
			pulseParameter.pulse()

		elif (parStyle == "Menu"):
			value = args[0]
			menuParameter = getattr(container.par, parName)
			labels = menuParameter.menuLabels
			values = menuParameter.menuNames
			index = labels.index(value)
			key = values[index]

			setattr(container.par, parName, key)

		else:
			setattr(container.par, parName, args[0])


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
									"type": par["TYPE"],
									"comp": compPath,
									"par": parameterName,
									"style": parameter.style,
									"firstTupletName": parameter.name
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
		hostinfo = {
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

		return hostinfo