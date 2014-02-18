import sys
import json

from pymel.core import *
from maya.OpenMaya import *
from maya.OpenMayaMPx import *

kPluginTranslatorTypeName = 'Three.js'
kOptionScript = 'ThreeJsExportScript'
kDefaultOptionsString = '0'

FLOAT_PRECISION = 8

class ThreeJsWriter(object):
    def __init__(self):
        self.componentKeys = ['vertices', 'normals', 'colors', 'materials', 'faces', 'bakeAnimations']

    def write(self, path, optionString, accessMode):
        self._parseOptions(optionString)

        self.vertices = []
        self.faces = []
        self.normals = []
        self.morphTargets = []

        if self.options["bakeAnimations"]:
            self._exportAnimations()
            self._goToFrame(self.options["startFrame"])
        self._exportMeshes()

        output = {
            'metadata': {
                'formatVersion': 3.1,
                'generatedBy': 'Maya Exporter'
            },

            'vertices': self.vertices,
            'faces': self.faces,
            'normals': self.normals,
            'morphTargets': self.morphTargets,
            'materials' : [{
                'DbgColor' : 15658734,
                'DbgIndex' : 0,
                'DbgName' : 'phong1.001',
                'blending' : 'NormalBlending',
                'colorAmbient' : [0.40519176133262746, 0.40519176133262746, 0.0],
                'colorDiffuse' : [0.40519176133262746, 0.40519176133262746, 0.0],
                'colorSpecular' : [0.25, 0.25, 0.25],
                'depthTest' : True,
                'depthWrite' : True,
                'shading' : 'Lambert',
                'specularCoef' : 20,
                'transparency' : 1.0,
                'transparent' : False,
                'vertexColors' : False
                }]
        }

        with file(path, 'w') as f:
            f.write(json.dumps(output, separators=(",",":")))

    def _parseOptions(self, optionsString):
        self.options = dict([(x, False) for x in self.componentKeys])
        for key in self.componentKeys:
            self.options[key] = key in optionsString
        if self.options["bakeAnimations"]:
            bakeAnimOptionsString = optionsString[optionsString.find("bakeAnimations"):]
            bakeAnimOptions = bakeAnimOptionsString.split(' ')
            self.options["startFrame"] = int(bakeAnimOptions[1])
            self.options["endFrame"] = int(bakeAnimOptions[2])
            self.options["stepFrame"] = int(bakeAnimOptions[3])

    def _exportMeshes(self):
        if self.options['vertices']:
            self._exportVertices()
        self._exportMesh(ls(type='mesh')[0])

    def _exportMesh(self, mesh):
        if self.options['faces']:
            self._exportFaces(mesh)
        if self.options['normals']:
            self._exportNormals(mesh)

    def _exportVertices(self):
        self.vertices += self._getVertices()

    def _exportAnimations(self):
        for frame in self._framesToExport():
            self._exportAnimationForFrame(frame)

    def _framesToExport(self):
        return range(self.options["startFrame"], self.options["endFrame"], self.options["stepFrame"])

    def _exportAnimationForFrame(self, frame):
        print("exporting frame " + str(frame))
        self._goToFrame(frame)
        self.morphTargets.append({
            'name': "frame_" + str(frame),
            'vertices': self._getVertices()
        })

    def _getVertices(self):
        return [coord for point in ls(type='mesh')[0].getPoints() for coord in [round(point.x, FLOAT_PRECISION), round(point.y, FLOAT_PRECISION), round(point.z, FLOAT_PRECISION)]]

    def _goToFrame(self, frame):
        currentTime(frame)

    def _numVertices(self):
        return sum([mesh.numVertices() for mesh in ls(type='mesh')])

    def _exportFaces(self, mesh):
        typeBitmask = self._getTypeBitmask()
        for face in mesh.faces:
            self._exportFaceBitmask(face, typeBitmask)
            self.faces += face.getVertices()
            if self.options['materials']:
                self.faces.append(0)
            if self.options['normals']:
                self._exportFaceVertexNormals(face)

    def _exportFaceBitmask(self, face, typeBitmask):
        if face.polygonVertexCount() == 4:
            faceBitmask = 1
        else:
            faceBitmask = 0
        self.faces.append(typeBitmask | faceBitmask)

    def _exportFaceVertexNormals(self, face):
        for i in range(face.polygonVertexCount()):
            self.faces.append(face.normalIndex(i))

    def _exportNormals(self, mesh):
        for normal in mesh.getNormals():
            self.normals += [round(normal.x, FLOAT_PRECISION), round(normal.y, FLOAT_PRECISION), round(normal.z, FLOAT_PRECISION)]

    def _getTypeBitmask(self):
        bitmask = 0
        if self.options['materials']:
            bitmask |= 2
        if self.options['normals']:
            bitmask |= 32
        return bitmask

class ThreeJsTranslator(MPxFileTranslator):
    def __init__(self):
        MPxFileTranslator.__init__(self)

    def haveWriteMethod(self):
        return True

    def filter(self):
        return '*.js'

    def defaultExtension(self):
        return 'js'

    def writer(self, fileObject, optionString, accessMode):
        path = fileObject.fullName()
        writer = ThreeJsWriter()
        writer.write(path, optionString, accessMode)


def translatorCreator():
    return asMPxPtr(ThreeJsTranslator())

def initializePlugin(mobject):
    mplugin = MFnPlugin(mobject)
    try:
        mplugin.registerFileTranslator(kPluginTranslatorTypeName, None, translatorCreator, kOptionScript, kDefaultOptionsString)
    except:
        sys.stderr.write('Failed to register translator: %s' % kPluginTranslatorTypeName)
        raise

def uninitializePlugin(mobject):
    mplugin = MFnPlugin(mobject)
    try:
        mplugin.deregisterFileTranslator(kPluginTranslatorTypeName)
    except:
        sys.stderr.write('Failed to deregister translator: %s' % kPluginTranslatorTypeName)
        raise

