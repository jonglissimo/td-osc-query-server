import json
import struct
from TDStoreTools import StorageManager
TDF = op.TDModules.mod.TDFunctions
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
		parType = stored["type"]
		parStyle = stored["style"]

		if (parStyle == "XY"):
			setattr(container.par, parName + "x", args[0])
			setattr(container.par, parName + "y", args[1])

		elif (parStyle == "XYZ"):
			setattr(container.par, parName + "x", args[0])
			setattr(container.par, parName + "y", args[1])
			setattr(container.par, parName + "z", args[2])

		elif (parStyle == "UV"):
			setattr(container.par, parName + "u", args[0])
			setattr(container.par, parName + "v", args[1])

		elif (parStyle == "UVW"):
			setattr(container.par, parName + "u", args[0])
			setattr(container.par, parName + "v", args[1])
			setattr(container.par, parName + "w", args[2])

		elif (parStyle == "WH"):
			setattr(container.par, parName + "w", args[0])
			setattr(container.par, parName + "h", args[1])
		
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

		# elif (len(parType) == 2):
		# 	setattr(container.par, parName + "x", args[0])
		# 	# setattr(container.par, parName + "y", args[1])


	def GetJson(self, uri="/"):
		if (uri == "/"):
			result = self.getFullJson()
			jsonText = TDJ.jsonToText(result)
			return jsonText
		
		else:
			result = self.getFullJson()
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


	def getFullJson(self):
		self.clearStorage() # clear storage, to rebuild on each request
		
		result = {
			"DESCRIPTION": "TD root node", 
			"CONTENTS": { } 
		}

		for i in range(1,11):
			compPath = getattr(self.ownerComp.par, "Comp" + str(i))
			container = self.ownerComp.op(compPath)

			if container:
				oscPrefix = self.getPrefix(container, i)
				includePagesInPath = getattr(self.ownerComp.par, "Includepagesinoscpath" + str(i))
				# print(compPath, oscPrefix, includePagesInPath)

				pars = TDJ.opToJSONOp(container, ["val"])
				pages = container.customPages
				compResult = {}
				contents = {}

				for pageObject in pages:
					pageName = pageObject.name
					page = pars[pageName]
					
					for i, (key, parameter) in enumerate(page.items()):
						# print(key, parameter)
						if (includePagesInPath):
							oscAddress = "/" + oscPrefix + "/" + pageName + "/" + key
						else:
							oscAddress = "/" + oscPrefix + "/" + key

						par = {}
						par["TYPE"] = self.getType(parameter)
						par["DESCRIPTION"] = key
						par["FULL_PATH"] = oscAddress

						if (par["TYPE"] != "N"):
							par["VALUE"] = self.getValue(parameter)

						if (par["TYPE"] != "s" and
							par["TYPE"] != "r" and
							par["TYPE"] != "N" or
							parameter["style"] == "Menu"):
							par["RANGE"] = self.getRange(parameter)

						contents[key] = par

						storageItem = { 
							"type": par["TYPE"],
							"comp": compPath,
							"par": key,
							"style": parameter["style"]
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
		valIsList = isinstance(parameter["val"], list)

		if (parameter["style"] == "XY" or
			parameter["style"] == "UV" or
			parameter["style"] == "WH"):
			if (valIsList):
				return [parameter["val"][0], parameter["val"][1]]
			else:
				return [parameter["val"], parameter["val"]]

		if (parameter["style"] == "XYZ" or 
			parameter["style"] == "UVW"):
			if (valIsList):
				return [parameter["val"][0], parameter["val"][1], parameter["val"][2]]
			else:
				return [parameter["val"], parameter["val"], parameter["val"]]

		if (parameter["style"] == "RGB" or
			parameter["style"] == "RGBA"):
			if (valIsList):
				r = self.getHex(parameter["val"][0])
				g = self.getHex(parameter["val"][1])
				b = self.getHex(parameter["val"][2])
				a = "ff" if parameter["style"] == "RGB" else self.getHex(parameter["val"][3])
				return ["#" + r + g + b + a]
			else:
				r = self.getHex(parameter["val"])
				g = self.getHex(parameter["val"])
				b = self.getHex(parameter["val"])
				a = "ff" if parameter["style"] == "RGB" else self.getHex(parameter["val"])
				return ["#" + r + g + b + a]

		if (parameter["style"] == "Menu"):
			curValue = parameter["val"]
			menuLabels = parameter["menuLabels"]
			menuNames = parameter["menuNames"]
			
			index = menuNames.index(curValue)
			key = menuLabels[index]
			
			return [key]

		return [parameter["val"]]

	def getHex(self, f):
		v = hex(int(f * 255))[2:]
		v = v if len(v) == 2 else "0" + str(v)
		return v

	def getRange(self, parameter):
		if (parameter["style"] == "Toggle"):
			return [{ "MAX": 1, "MIN": 0 }]

		if (parameter["style"] == "XY" or
			parameter["style"] == "UV" or
			parameter["style"] == "WH"):
			maxIsList = isinstance(parameter["normMax"], list)
			minIsList = isinstance(parameter["normMin"], list)

			max1 = parameter["normMax"][0] if maxIsList else parameter["normMax"]
			min1 = parameter["normMin"][0] if minIsList else parameter["normMin"]
			max2 = parameter["normMax"][1] if maxIsList else parameter["normMax"]
			min2 = parameter["normMin"][1] if minIsList else parameter["normMin"]

			return [{ "MAX": max1, "MIN": min1 }, { "MAX": max2, "MIN": min2 }]

		if (parameter["style"] == "XYZ" or
			parameter["style"] == "UVW"):
			maxIsList = isinstance(parameter["normMax"], list)
			minIsList = isinstance(parameter["normMin"], list)

			max1 = parameter["normMax"][0] if maxIsList else parameter["normMax"]
			min1 = parameter["normMin"][0] if minIsList else parameter["normMin"]
			max2 = parameter["normMax"][1] if maxIsList else parameter["normMax"]
			min2 = parameter["normMin"][1] if minIsList else parameter["normMin"]
			max3 = parameter["normMax"][2] if maxIsList else parameter["normMax"]
			min3 = parameter["normMin"][2] if minIsList else parameter["normMin"]

			return [{ "MAX": max1, "MIN": min1 }, { "MAX": max2, "MIN": min2 }, { "MAX": max3, "MIN": min3 }]

		if (parameter["style"] == "Menu"):
			return [{ "VALS": parameter["menuLabels"]}]

		if ("normMax" in parameter and "normMin" in parameter):
			return [{ "MAX": parameter["normMax"], "MIN": parameter["normMin"] }]
			

	def getType (self, parameter):
		t = parameter["style"]

		if (t == "Float"):
			return "f"
		elif (t == "Int"):
			return "i"
		elif (t == "Str" or 
			t == "File" or 
			t == "Folder" or
			t == "CHOP" or
			t == "COMP" or
			t == "DAT" or
			t == "SOP" or
			t == "MAT" or
			t == "TOP" or
			t == "Menu" or
			t == "StrMenu"):
			return "s"
		elif (t == "Toggle"):
			return "T"
		elif (t == "RGB" or
			t == "RGBA"):
			return "r"
		elif (t == "XY" or
			t == "UV" or
			t == "WH"):
			return "ff"
		elif (t == "XYZ" or
			t == "UVW"):
			return "fff"
		elif (t == "Pulse"):
			return "N"
		

		return "f"

	
	def getPrefix(self, container, i):
		if not container:
			return ""
			
		customPrefix = str(getattr(self.ownerComp.par, "Oscprefix" + str(i)))

		if not customPrefix:
				return str(container.name)
		else:
			return customPrefix