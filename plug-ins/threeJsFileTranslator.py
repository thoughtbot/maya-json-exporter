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
        self.componentKeys = ['vertices', 'normals', 'colors', 'materials', 'faces', 'bones', 'bakeAnimations']

    def write(self, path, optionString, accessMode):
        self._parseOptions(optionString)

        self.vertices = []
        self.materials = []
        self.faces = []
        self.normals = []
        self.morphTargets = []
        self.bones = []

        if self.options["bakeAnimations"]:
            self._exportAnimations()
            self._goToFrame(self.options["startFrame"])
        if self.options["materials"]:
            self._exportMaterials()
        if self.options["bones"]:
            self._exportBones()
        self._exportMeshes()

        output = {
            'metadata': {
                'formatVersion': 3.1,
                'generatedBy': 'Maya Exporter'
            },

            'vertices': self.vertices,
            'faces': self.faces,
            'normals': self.normals,
            'materials': self.materials,
        }

        if self.options['bakeAnimations']:
            output['morphTargets'] = self.morphTargets

        if self.options['bones']:
            output['bones'] = self.bones

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
        for mesh in ls(type='mesh'):
            self._exportMesh(mesh)

    def _exportMesh(self, mesh):
        materialIndex = self._getMaterialIndex(mesh)
        if self.options['faces']:
            self._exportFaces(mesh, materialIndex)
        if self.options['normals']:
            self._exportNormals(mesh)

    def _getMaterialIndex(self, mesh):
        if self.options['materials']:
            for engine in mesh.listConnections(type='shadingEngine'):
                for material in engine.listConnections(type='lambert'):
                    for i in range(0, len(self.materials)):
                        serializedMat = self.materials[i]
                        if serializedMat['DbgName'] == material.name():
                            return i
        return -1


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
        return [coord for mesh in ls(type='mesh') for point in mesh.getPoints() for coord in [round(point.x, FLOAT_PRECISION), round(point.y, FLOAT_PRECISION), round(point.z, FLOAT_PRECISION)]]

    def _goToFrame(self, frame):
        currentTime(frame)

    def _numVertices(self):
        return sum([mesh.numVertices() for mesh in ls(type='mesh')])

    def _exportFaces(self, mesh, materialIndex):
        typeBitmask = self._getTypeBitmask()
        hasMaterial = materialIndex != -1

        for face in mesh.faces:
            self._exportFaceBitmask(face, typeBitmask, hasMaterial=hasMaterial)
            self.faces += face.getVertices()
            if self.options['materials']:
                if hasMaterial:
                    self.faces.append(materialIndex)
            if self.options['normals']:
                self._exportFaceVertexNormals(face)

    def _exportFaceBitmask(self, face, typeBitmask, hasMaterial=True):
        if face.polygonVertexCount() == 4:
            faceBitmask = 1
        else:
            faceBitmask = 0
        if hasMaterial:
            faceBitmask |= 2
        self.faces.append(typeBitmask | faceBitmask)

    def _exportFaceVertexNormals(self, face):
        for i in range(face.polygonVertexCount()):
            self.faces.append(face.normalIndex(i))

    def _exportNormals(self, mesh):
        for normal in mesh.getNormals():
            self.normals += [round(normal.x, FLOAT_PRECISION), round(normal.y, FLOAT_PRECISION), round(normal.z, FLOAT_PRECISION)]

    def _getTypeBitmask(self):
        bitmask = 0
        if self.options['normals']:
            bitmask |= 32
        return bitmask

    def _exportMaterials(self):
        for mat in ls(type='lambert'):
            self.materials.append(self._exportMaterial(mat))

    def _exportMaterial(self, mat):
        result = {
            "DbgName": mat.name(),
            "blending": "NormalBlending",
            "colorDiffuse": map(lambda i: i * mat.getDiffuseCoeff(), mat.getColor().rgb),
            "colorAmbient": mat.getAmbientColor().rgb,
            "depthTest": True,
            "depthWrite": True,
            "shading": mat.__class__.__name__,
            "transparency": mat.getTransparency().a,
            "transparent": mat.getTransparency().a != 1.0,
            "vertexColors": False
        }
        if isinstance(mat, nodetypes.Phong):
            result["colorSpecular"] = mat.getSpecularColor().rgb
            result["specularCoef"] = mat.getCosPower()

        return result

    def _exportBones(self):
        joints = ls(type='joint')
        jointNames = map(lambda j: j.name(), joints)

        for joint in joints:

            parentIndex = -1
            for i in range(0, len(jointNames)):
                if jointNames[i] == joint.getParent().name():
                    parentIndex = i

            self.bones.append({
                "parent": parentIndex,
                "name": joint.name(),
                "pos": [],
                "rotq": []
            })

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

