import json
import struct
from TDStoreTools import StorageManager
import osc_parse_module as osclib
TDJ = op.TDModules.mod.TDJSON

webserver = op("webserver1")
monitor_changes = op("monitor_changes")


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

		if parStyle in ["Float", "XY", "XYZ", "UV", "UVW", "WH"]:
			for i, p in enumerate(parameter.tuplet):
				p.val = args[i]

			stored["lastReceivedValue"] = args

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
			
			stored["lastReceivedValue"] = color
			
		elif parStyle == "Pulse":
			parameter.pulse()

		elif parStyle == "Momentary":
			parameter.pulse(frames=1)

		elif parStyle == "Menu":
			value = args[0]
			labels = parameter.menuLabels
			values = parameter.menuNames
			index = labels.index(value)
			key = values[index]
			parameter.val = key
			stored["lastReceivedValue"] = key

		else:
			parameter.val = args[0]
			stored["lastReceivedValue"] = args[0]


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
		self.destroyBidirectional()

		bidirectionalActivated = parent().par.Bidirectionalcommunication
		
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
							par = self.getParameterDefinition(parameter, oscPrefix, includePagesInPath, pageName)
							if par:
								parameterName = par["DESCRIPTION"]
								contents[parameterName] = par
							
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

				if bidirectionalActivated:
					self.setupBidirectional(container)

		return result

	
	def getParameterDefinition(self, parameter, oscPrefix, includePagesInPath, pageName):
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

			storageItem = { 
				"address": oscAddress,
				"type": par["TYPE"],
				"par": parameter
			}

			self.ownerComp.store(oscAddress, storageItem)
			print(oscAddress)

			container = parameter.owner

			for t in parameter.tuplet:
				key = container.name + "." + t.name
				self.ownerComp.store(key, storageItem)

			return par


	def GetUpdateMsg(self, container, parameter, force=False):
		key = container.name + "." + parameter.name
		storedItem = parent().fetch(key)
		par = storedItem["par"]
		address = storedItem["address"]

		if self.checkLastReceivedValue(storedItem, par) and not force:
			return False

		typeString = "," + storedItem["type"]
		values = self.getValueForUpdate(par)

		if par.style == "Toggle":
			typeString = ",i"

			if par.eval():
				values = [1]
			else:
				values = [0]

		msg = osclib.OSCMessage(address, typeString, values)
		raw = osclib.encode_packet(msg)

		return {
			"address": address,
			"rawMsg": raw 
		}


	def checkLastReceivedValue(self, storedItem, parameter):
		if "lastReceivedValue" in storedItem.keys(): 
			parStyle = parameter.style

			if parStyle in ["Float", "XY", "XYZ", "UV", "UVW", "WH", "RGB", "RGBA"]:
				for i, p in enumerate(parameter.tuplet):
					if p.eval() != storedItem["lastReceivedValue"][i]:
						return False
				return True
			else:
				return storedItem["lastReceivedValue"] == parameter.eval()
		else: 
			return False



	def getValue(self, parameter):
		size = len(parameter.tuplet)

		if (parameter.style in ["Float", "XY", "UV", "WH", "XYZ", "UVW"]):
			if size == 1:
				return [parameter.tuplet[0].eval()]
			elif size == 2:
				return [parameter.tuplet[0].eval(), parameter.tuplet[1].eval()]
			elif size == 3:
				return [parameter.tuplet[0].eval(), parameter.tuplet[1].eval(), parameter.tuplet[2].eval()]
			elif size == 4: 
				return [parameter.tuplet[0].eval(), parameter.tuplet[1].eval(), parameter.tuplet[2].eval(), parameter.tuplet[3].eval()]

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



	def getValueForUpdate(self, parameter):
		size = len(parameter.tuplet)

		if (parameter.style in ["Float", "XY", "UV", "WH", "XYZ", "UVW"]):
			if size == 1:
				return [parameter.tuplet[0].eval()]
			elif size == 2:
				return [parameter.tuplet[0].eval(), parameter.tuplet[1].eval()]
			elif size == 3:
				return [parameter.tuplet[0].eval(), parameter.tuplet[1].eval(), parameter.tuplet[2].eval()]
			elif size == 4: 
				return [parameter.tuplet[0].eval(), parameter.tuplet[1].eval(), parameter.tuplet[2].eval(), parameter.tuplet[3].eval()]

		if (parameter.style in ["RGB", "RGBA"]):
			r = self.floatToInt(parameter.tuplet[0].eval())
			g = self.floatToInt(parameter.tuplet[1].eval())
			b = self.floatToInt(parameter.tuplet[2].eval())
			a = 255 if parameter.style == "RGB" else self.floatToInt(parameter.tuplet[3].eval())

			return [osclib.OSCrgba(r, g, b, a)]

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

	def floatToInt(self, f):
		return int(f * 255) 

	def getHex(self, f):
		v = hex(int(f * 255))[2:]
		v = v if len(v) == 2 else "0" + str(v)
		return v


	def getRange(self, parameter):
		size = len(parameter.tuplet)

		if (parameter.style == "Toggle"):
			return [{ "MAX": 1, "MIN": 0 }]

		if (parameter.style in ["Float", "XY", "UV", "WH", "XYZ", "UVW"]):
			result = []

			for i in range(size):
				newRange = { "MAX": parameter.tuplet[i].normMax, "MIN": parameter.tuplet[i].normMin }
				result.append(newRange)

			return result

		if (parameter.style == "Menu"):
			return [{ "VALS": parameter.menuLabels }]

		return [{ "MAX": parameter.normMax, "MIN": parameter.normMin }]


	def getType (self, parameter):
		t = parameter.style
		size = len(parameter.tuplet)

		if (t in ["Float", "XY", "UV", "WH", "XYZ", "UVW"]):
			return "f" * size
		elif (t == "Int"):
			return "i" * size
		elif (t in ["Str", "File", "Folder", "CHOP", "COMP", "DAT", "SOP", "MAT", "TOP", "Menu", "StrMenu"]):
			return "s"
		elif (t == "Toggle"):
			if parameter.eval():
				return "T"
			else:
				return "F"
		elif (t in ["RGB", "RGBA"]):
			return "r"
		elif (t in ["Pulse", "Momentary"]):
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
		bidirectionalActivated = parent().par.Bidirectionalcommunication.eval()

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
					"LISTEN": bidirectionalActivated,
					"RANGE": True,
					"HTML": False,
					"PATH_ADDED": False,
					"UNIT": False,
					"ACCESS": True,
					"IGNORE": False,
					"TAGS": False
				}
		}

	def ActivateBidirectional(self):
		self.GetJson()
	
	def DeactivateBidirectional(self):
		children = monitor_changes.findChildren(type=parameterexecuteDAT)

		for c in children:
			c.par.active = False
	
	def destroyBidirectional(self):
		children = monitor_changes.findChildren(type=parameterexecuteDAT)

		for c in children:
			c.destroy()

	def setupBidirectional(self, container):
		createdOP = monitor_changes.copy(op("parexec_template"), name=container.name)
		createdOP.par.op = container.path
		createdOP.par.active = True


	def ClearListenData(self):
		monitor_changes.unstore("/*")

	def AddToListen(self, address, client):
		try: 
			listeningClients = monitor_changes.fetch(address)

			if client not in listeningClients:
				listeningClients.append(client)
				monitor_changes.store(address, listeningClients)

		except Exception:
			monitor_changes.store(address, [ client ])

	def RemoveFromListen(self, address, client):
		try:
			listeningClients = monitor_changes.fetch(address)
			listeningClients.remove(client)
			monitor_changes.store(address, listeningClients)
		except Exception:
			pass
	
	def IsListeningToClient(self, address, client):
		listeningClients = monitor_changes.fetch(address)
		return client in listeningClients
