#!/usr/bin/env python
""" Implements a "ground truth" odometry using the model state information from Gazebo.
"""

import numpy as np
import rospy
import tf2_ros
from tf import transformations as trf
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Transform,Pose,PoseWithCovariance,Twist,TwistWithCovariance
from gazebo_msgs.msg import ModelState,ModelStates


# Functions for convenience
def transform_between_poses(pb, pf):
    """ Returns the transform between the follower frame F with pose pf, and the base
    frame B with pose pb. That is the transform g 
    g = g_{bf} = inv(pb) * pf.
    Note that the pose pb is equivalent to the transform g_{sb} and pf equivalent to g_{sf}, so
    g = g_{bs} * g_{sf} = inv(g_{sb}) * g_{sf} = inv(pb) * pf. This can be rewritten as
    pf = pb * g.
    So the transform g transforms points given in the frame F to B, and then these points are 
    transformed to the spatial frame S.
    """

    g_sb = pose2np(pb)
    g_sf = pose2np(pf)

    g = np.dot(np.linalg.inv(g_sb), g_sf)
    t = Transform()
    np2trf(g, t)

    return t
    
def pose2np(p):
    """ Returns a 4x4 numpy matrix representing the rigid transformation of the given Pose or
    Transform object.
    """
    a = np.eye(4);
    if isinstance(p, Pose):
        q = np.array([p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w])
        qmat = trf.quaternion_matrix(q)
        a[:3, :3] = qmat[:3, :3] 
        a[:3, 3] = [p.position.x, p.position.y, p.position.z]
    if isinstance(p, Transform):
        q = np.array([p.rotation.x, p.rotation.y, p.rotation.z, p.rotation.w])
        a[:, :] = trf.quaternion_matrix(q)
        a[:3, 3] = [p.translation.x, p.translation.y, p.translation.z]
    return a

def np2trf(a, t):
    t.translation.x = a[0,3]
    t.translation.y = a[1,3]
    t.translation.z = a[2,3]

    q = trf.quaternion_from_matrix(a)
    t.rotation.x = q[0]
    t.rotation.y = q[1]
    t.rotation.z = q[2]
    t.rotation.w = q[3]
    
def np2pose(a, p):
    p.position.x = a[0,3]
    p.position.y = a[1,3]
    p.position.z = a[2,3]

    q = trf.quaternion_from_matrix(a)
    p.orientation.x = q[0]
    p.orientation.y = q[1]
    p.orientation.z = q[2]
    p.orientation.w = q[3]

def transform_vector(t, v1, inverse=False):
    """ Transforms the vector v given the transformation t. 
    Implementation from 
    https://answers.ros.org/question/196149/how-to-rotate-vector-by-quaternion-in-python/
    """

    q1 = t.rotation
    q2 = list(v1)
    q2.append(0.0)
    if inverse:
        return trf.quaternion_multiply(
            trf.quaternion_conjugate(q1),
            trf.quaternion_multiply(q2, q1), 

        )[:3]
    else:
        return trf.quaternion_multiply(
            trf.quaternion_multiply(q1, q2), 
            trf.quaternion_conjugate(q1)
        )[:3]
    
class OdometryPublisher():
    def __init__(self):

        rospy.init_node('ReferenceOdometryPublisher')

        # Subscribe to the model_states topic to obtain the position and heading of the puzzlebot
        rospy.Subscriber("gazebo/model_states", ModelStates, self.callback)
        # Publish the bot pose to a topic
        self.odom_pub = rospy.Publisher("/true_odometry", Odometry)
        
        self.model_state = None
        self.model_twist = None
        self.initial_state = None
        self.bot_pose = PoseStamped()

        # For broadcasting transform from base_link to odom_true 
        self.br = tf2_ros.TransformBroadcaster() 
        # For broadcasting the static transform from odom_true to world
        self.brStatic = tf2_ros.StaticTransformBroadcaster()

    def main(self):

        # If there's an object attached to the ee we want it to follow its trajectory
        while not rospy.is_shutdown():
            if self.initial_state is None:
                if self.model_state is not None:
                    # Get the initial pose 
                    t = PoseStamped()
                    t.header.stamp = rospy.Time.now()
                    t.header.frame_id = "world"
                    t.child_frame_id = "odom_true"
                    t.transform.translation = self.model_state.pose.position
                    t.transform.rotation = self.model_state.pose.orientation
                    self.initial_state = t
                    self.brStatic.sendTransform(t)
            if self.model_state is not None:
                # Publish the state of the puzzlebot
                t = TransformStamped()
                t.header.stamp = rospy.Time.now()
                t.header.frame_id = "odom_true"
                t.child_frame_id = "base_link"

                tt = transform_between_poses(self.initial_state, self.model_state)

                t.transform.translation = tt.translation
                t.transform.rotation = tt.rotation
                self.br.sendTransform(t)

                # Publish the odometry message
                odom = Odometry()
                odom.header.stamp = t.header.stamp
                odom.header.frame_id = "odom_true"
                # Set the position
                odom.pose.pose = Pose(t.transform.translation, t.transform.rotation)
                # Set the velocity
                odom.child_frame_id = "base_link"
                vs = self.model_twist.linear # Velocity of puzzlebot in world frame
                tr = Transform()
                tr.rotation = self.model_state.orientation
                vb = transform_vector(tr, vs, inverse=True) # Transform to base_link frame
                odom.twist.twist = Twist(Vector3(*vb), Vector3(0,0,this.model_twist.angular[2])

                # publish the message
                self.odom_pub.publish(odom)

                
    def callback(self, data):
        aux_idx = data.name.index('puzzlebot')

        self.model_state = data.pose[ux_idx]
        self.model_twist = data.twist[ux_idx]
        
if __name__ == '__main__':

    try:
        aux = OdometryPublisher()
        aux.main()

    except (rospy.ROSInterruptException, rospy.ROSException("topic was closed during publish()")):
        pass