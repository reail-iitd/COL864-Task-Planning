from collections import namedtuple
from attrdict import AttrDict
import pybullet as p
import functools

joints = {}
userParams = {}
controlJoints = []
mimicParentName = ""

def initGripper(robotID):
    global joints, controlJoints, userParams
    controlJoints = ["shoulder_pan_joint","shoulder_lift_joint",
                     "elbow_joint", "wrist_1_joint",
                     "wrist_2_joint", "wrist_3_joint",
                     "robotiq_85_left_knuckle_joint"]
    jointTypeList = ["REVOLUTE", "PRISMATIC", "SPHERICAL", "PLANAR", "FIXED"]
    numJoints = p.getNumJoints(robotID)
    jointInfo = namedtuple("jointInfo", 
                           ["id","name","type","lowerLimit","upperLimit","maxForce","maxVelocity","controllable"])
    joints = AttrDict()

    for i in range(numJoints):
        info = p.getJointInfo(robotID, i)
        jointID = info[0]
        jointName = info[1].decode("utf-8")
        jointType = jointTypeList[info[2]]
        jointLowerLimit = info[8]
        jointUpperLimit = info[9]
        jointMaxForce = info[10]
        jointMaxVelocity = info[11]
        controllable = True if jointName in controlJoints else False
        info = jointInfo(jointID,jointName,jointType,jointLowerLimit,
                         jointUpperLimit,jointMaxForce,jointMaxVelocity,controllable)
        if info.type=="REVOLUTE": # set revolute joint to static
            p.setJointMotorControl2(robotID, info.id, p.VELOCITY_CONTROL, targetVelocity=0, force=0)
        joints[info.name] = info

    userParams = dict()
    for name in controlJoints:
        joint = joints[name]
        userParam = p.addUserDebugParameter(name, joint.lowerLimit, joint.upperLimit, 0)
        userParams[name] = userParam

    return controlJoints, joints

def controlGripper(robotID, parent, children, mul, **kwargs):
    controlMode = kwargs.pop("controlMode")
    if controlMode==p.POSITION_CONTROL:
        pose = kwargs.pop("targetPosition")
        # move parent joint
        p.setJointMotorControl2(robotID, parent.id, controlMode, targetPosition=pose, 
                                force=parent.maxForce, maxVelocity=parent.maxVelocity) 
        # move child joints
        for name in children:
            child = children[name]
            childPose = pose * mul[child.name]
            p.setJointMotorControl2(robotID, child.id, controlMode, targetPosition=childPose, 
                                    force=child.maxForce, maxVelocity=child.maxVelocity) 
    else:
        raise NotImplementedError("controlGripper does not support \"{}\" control mode".format(controlMode))
    # check if there 
    if len(kwargs) is not 0:
        raise KeyError("No keys {} in controlGripper".format(", ".join(kwargs.keys())))

def getUR5ControllerHelper(robotID):
    global mimicParentName, controlRobotiqC2
    mimicParentName = "robotiq_85_left_knuckle_joint"
    mimicChildren = {"robotiq_85_right_knuckle_joint":      1,
                     "robotiq_85_right_finger_joint":       1,
                     "robotiq_85_left_inner_knuckle_joint": 1,
                     "robotiq_85_left_finger_tip_joint":    1,
                     "robotiq_85_right_inner_knuckle_joint":1,
                     "robotiq_85_right_finger_tip_joint":   1}
    parent = joints[mimicParentName] 
    children = AttrDict((j, joints[j]) for j in joints if j in mimicChildren.keys())
    controlRobotiqC2 = functools.partial(controlGripper, robotID, parent, children, mimicChildren)
    return controlRobotiqC2
 
def getUR5Controller(robotID):
    controlFunction = getUR5ControllerHelper(robotID)
    def control(robotID, wing):
        for name in controlJoints:
            joint = joints[name]
            pose = wing[name]
            if name==mimicParentName:
                controlFunction(controlMode=p.POSITION_CONTROL, targetPosition=pose)
            else:
                p.setJointMotorControl2(robotID, joint.id, p.POSITION_CONTROL,
                                            targetPosition=pose, force=joint.maxForce, 
                                            maxVelocity=joint.maxVelocity)
    return control
