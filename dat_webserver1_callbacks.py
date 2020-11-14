# me - this DAT.
# webServerDAT - the connected Web Server DAT
# request - A dictionary of the request fields. The dictionary will always contain the below entries, plus any additional entries dependent on the contents of the request
# 		'method' - The HTTP method of the request (ie. 'GET', 'PUT').
# 		'uri' - The client's requested URI path. If there are parameters in the URI then they will be located under the 'pars' key in the request dictionary.
#		'pars' - The query parameters.
# 		'clientAddress' - The client's address.
# 		'serverAddress' - The server's address.
# 		'data' - The data of the HTTP request.
# response - A dictionary defining the response, to be filled in during the request method. Additional fields not specified below can be added (eg. response['content-type'] = 'application/json').
# 		'statusCode' - A valid HTTP status code integer (ie. 200, 401, 404). Default is 404.
# 		'statusReason' - The reason for the above status code being returned (ie. 'Not Found.').
# 		'data' - The data to send back to the client. If displaying a web-page, any HTML would be put here.

# return the response dictionary
import osc_parse_module as osclib
import json


def onHTTPRequest(webServerDAT, request, response):
	uri = request["uri"]
	uriSegments = uri.split("/")

	if "client.js" in request["pars"]:
		response = addToResponse(response, 200, "application/javascript")
		response["data"] = op("web_assets/client_js").text

	elif "style.css" in request["pars"]:
		response = addToResponse(response, 200, "text/css")
		response["data"] = op("web_assets/style_css").text

	elif uri == "/ui":
		response = addToResponse(response, 200, "text/html")
		html = op("web_assets/edit_html").text
		html = insertHostURL(html, request["serverAddress"])
		response["data"] = html

	elif len(uriSegments) > 1 and uriSegments[1] == "fonts":	# don't return anything for the missing fonts requested by web client
		pass

	else:
		try:
			response = addToResponse(response, 200, "application/json")
			response["Access-Control-Allow-Origin"] = "*"
			response["data"] = parent().GetJson(uri, request["pars"])
		except:
			response = addToResponse(response, 404, "text/html")
			response["data"] = buildNotFoundData()

	return response


def onWebSocketOpen(webServerDAT, client):
	print("OSCQuery websocket opened for client: " + client)
	return


def onWebSocketClose(webServerDAT, client):
	print("OSCQuery websocket closed for client: " + client)
	return


def onWebSocketReceiveText(webServerDAT, client, data):
	safeData = data.split("}")[0] + "}"  # hack needed because of integrated osc query webclient behaving weird
	obj = json.loads(safeData) 

	if obj["COMMAND"] == "LISTEN":
		parent().AddToListen(obj["DATA"], client)
	elif obj["COMMAND"] == "IGNORE":
		parent().RemoveFromListen(obj["DATA"], client)

	return


def onWebSocketReceiveBinary(webServerDAT, client, data):
	msg = osclib.decode_packet(data)
	oscAddress = msg.addrpattern
	oscArgs = []

	for arg in msg.arguments:
		if hasattr(arg, "red"):
			for c in arg:
				color = c / 255
				oscArgs.append(color)

		oscArgs.append(arg)
		
	parent().ReceiveOsc(oscAddress, oscArgs)
	
	return


def onWebSocketReceivePing(webServerDAT, client, data):
	return


def onWebSocketReceivePong(webServerDAT, client, data):
	return


def onServerStart(webServerDAT):
	print("Started OSC Query Server")
	return


def onServerStop(webServerDAT):
	print("Stopped OSC Query Server")
	return




# HELPER FUNCTIONS

def addToResponse(response, statusCode, contentType):
	response["statusCode"] = statusCode
	
	if (statusCode == 200):
		response["statusReason"] = "OK"
	elif (statusCode == 404):
		response["statusReason"] = "Not found"

	response["content-type"] = contentType

	return response


def insertHostURL(html, url):
	html = html.replace("HOST_URL", url)
	return html


def buildNotFoundData():
	oscAddresses = parent().GetAllAddresses()

	data = "<h1>Not Found</h1>"
	data = data + "No container or method was found at the supplied OSC address<br><br>"
	data = data + "The following OSC addresses are available<br><ul>"

	for a in oscAddresses:
		data = data + "<li>" + a + "</li>"

	data = data + "</ul>"

	return data
