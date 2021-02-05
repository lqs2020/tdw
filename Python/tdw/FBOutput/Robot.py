# automatically generated by the FlatBuffers compiler, do not modify

# namespace: FBOutput

import tdw.flatbuffers

class Robot(object):
    __slots__ = ['_tab']

    @classmethod
    def GetRootAsRobot(cls, buf, offset):
        n = tdw.flatbuffers.encode.Get(tdw.flatbuffers.packer.uoffset, buf, offset)
        x = Robot()
        x.Init(buf, n + offset)
        return x

    # Robot
    def Init(self, buf, pos):
        self._tab = tdw.flatbuffers.table.Table(buf, pos)

    # Robot
    def Id(self):
        o = tdw.flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            return self._tab.Get(tdw.flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 0

    # Robot
    def Transform(self):
        o = tdw.flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(6))
        if o != 0:
            x = o + self._tab.Pos
            from .SimpleTransform import SimpleTransform
            obj = SimpleTransform()
            obj.Init(self._tab.Bytes, x)
            return obj
        return None

    # Robot
    def Joints(self, j):
        o = tdw.flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(8))
        if o != 0:
            x = self._tab.Vector(o)
            x += tdw.flatbuffers.number_types.UOffsetTFlags.py_type(j) * 4
            x = self._tab.Indirect(x)
            from .RobotJoint import RobotJoint
            obj = RobotJoint()
            obj.Init(self._tab.Bytes, x)
            return obj
        return None

    # Robot
    def JointsLength(self):
        o = tdw.flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(8))
        if o != 0:
            return self._tab.VectorLen(o)
        return 0

def RobotStart(builder): builder.StartObject(3)
def RobotAddId(builder, id): builder.PrependInt32Slot(0, id, 0)
def RobotAddTransform(builder, transform): builder.PrependStructSlot(1, tdw.flatbuffers.number_types.UOffsetTFlags.py_type(transform), 0)
def RobotAddJoints(builder, joints): builder.PrependUOffsetTRelativeSlot(2, tdw.flatbuffers.number_types.UOffsetTFlags.py_type(joints), 0)
def RobotStartJointsVector(builder, numElems): return builder.StartVector(4, numElems, 4)
def RobotEnd(builder): return builder.EndObject()
