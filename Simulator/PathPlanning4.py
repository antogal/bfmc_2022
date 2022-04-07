#!/usr/bin/python3
from time import time, sleep
import copy
import networkx as nx
import numpy as np
import cv2 as cv
from pyclothoids import Clothoid

from helper_functions import *

class PathPlanning(): 
    def __init__(self, map_img):
        # start and end nodes
        self.source = str(86)
        self.target = str(300)

        # initialize path
        self.path = []
        self.navigator = []# set of instruction for the navigator
        self.path_data = [] #additional data for the path (e.g. curvature, 
        self.step_length = 0.01
        # state=following/intersection/roundabout, next_action=left/right/straight, path_params_ahead)

        # previous index of the closest point on the path to the vehicle
        self.prev_index = 0

        # read graph
        self.G = nx.read_graphml('data/Competition_track.graphml')
        # initialize route subgraph and list for interpolation
        self.route_graph = nx.DiGraph()
        self.route_list = []
        self.old_nearest_point_index = None # used in search target point

        # define intersection central nodes
        #self.intersection_cen = ['347', '37', '39', '38', '11', '29', '30', '28', '371', '84', '9', '20', '20', '82', '75', '74', '83', '312', '315', '65', '468', '10', '64', '57', '56', '66', '73', '424', '48', '47', '46']
        self.intersection_cen = ['37', '39', '38', '11', '29', '30', '28', '371', '84', '9','19', '20', '21', '82', '75', '74', '83', '312', '315', '65', '10', '64', '57', '56', '66', '73', '424', '48', '47', '46']

        # define intersecion entrance nodes
        self.intersection_in = [77,45,54,50,41,79,374,52,43,81,36,4,68,2,34,70,6,32,72,59,15,16,27,14,25,18,61,23,63]
        self.intersection_in = [str(i) for i in self.intersection_in]

        # define intersecion exit nodes
        self.intersection_out = [76,78,80,40,42,44,49,51,53,67,69,71,1,3,5,7,8,31,33,35,22,24,26,13,17,58,60,62]
        self.intersection_out = [str(i) for i in self.intersection_out]

        # define left turns tuples
        #self.left_turns = [(45,42),(43,40),(54,51),(36,33),(34,31),(6,3),(2,7),(2,8),(4,1),(70,67),(72,69),(27,24),(25,22),(16,13),(61,58),(63,60)]

        #define crosswalks 
        self.crosswalk = [92,96,276,295,170,266,177,162] #note: parking spots are included too (177,162)
        self.crosswalk = [str(i) for i in self.crosswalk]

        # define roundabout nodes
        self.ra = [267,268,269,270,271,302,303,304,305,306,307]
        self.ra = [str(i) for i in self.ra]

        self.ra_enter = [301,342,230] #[267,302,305]
        self.ra_enter = [str(i) for i in self.ra_enter]

        self.ra_exit = [272,231,343] # [271,304,306]
        self.ra_exit = [str(i) for i in self.ra_exit]

        self.junctions = [467,314]
        self.junctions = [str(i) for i in self.junctions]

        #stop line points
        self.stop_line_points = np.load('data/stop_line_points.npy')
        self.stop_line_types = np.load('data/stop_line_types.npy')
        assert len(self.stop_line_points) == len(self.stop_line_types), "stop line points and types are not the same length"
        type_names = [
            'intersection_stop',
            'intersection_traffic_light',
            'intersection_priority', 
            'junction',
            'roundabout',
            'crosswalk',
        ]
        self.stop_line_types = [type_names[int(i)] for i in self.stop_line_types]

        # import nodes and edges
        self.list_of_nodes = list(self.G.nodes)
        self.list_of_edges = list(self.G.edges)

        self.nodes_data = self.G.nodes.data()
        self.edges_data = self.G.edges.data()

        # import map to plot trajectory and car
        self.map = map_img

    def roundabout_navigation(self, prev_node, curr_node, next_node):
        while next_node in self.ra:
            prev_node = curr_node
            curr_node = next_node
            if curr_node != self.target:
                next_node = list(self.route_graph.successors(curr_node))[0]
            else:
                next_node = None
                break
                
            #print("inside roundabout: ", curr_node)
            
            xp,yp = self.get_coord(prev_node)
            xc,yc = self.get_coord(curr_node)
            xn,yn = self.get_coord(next_node)

            if curr_node in self.ra_enter:
                if not(prev_node in self.ra):
                    dx = xn - xp
                    dy = yn - yp
                    self.route_list.append((xc,yc,np.rad2deg(np.arctan2(dy,dx))))
                else:
                    if curr_node == '302':
                        continue
                    else:
                        dx = xn - xp
                        dy = yn - yp
                        self.route_list.append((xc,yc,np.rad2deg(np.arctan2(dy,dx))))
            elif curr_node in self.ra_exit:
                if next_node in self.ra:
                    # remain inside roundabout
                    if curr_node == '271':
                        continue
                    else:
                        dx = xn - xp
                        dy = yn - yp
                        self.route_list.append((xc,yc,np.rad2deg(np.arctan2(dy,dx))))
                else:
                    dx = xn - xp
                    dy = yn - yp
                    self.route_list.append((xc,yc,np.rad2deg(np.arctan2(dy,dx))))
            else:
                dx = xn - xp
                dy = yn - yp
                self.route_list.append((xc,yc,np.rad2deg(np.arctan2(dy,dx))))

        prev_node = curr_node
        curr_node = next_node
        if curr_node != self.target:
            next_node = list(self.route_graph.successors(curr_node))[0]
        else:
            next_node = None
        
        self.navigator.append("exit roundabout at "+curr_node)
        self.navigator.append("go straight")
        return prev_node, curr_node, next_node
    
    def intersection_navigation(self, prev_node, curr_node, next_node):
        prev_node = curr_node
        curr_node = next_node
        if curr_node != self.target:
            next_node = list(self.route_graph.successors(curr_node))[0]
        else:
            next_node = None
            return prev_node, curr_node, next_node
        
        prev_node = curr_node
        curr_node = next_node
        if curr_node != self.target:
            next_node = list(self.route_graph.successors(curr_node))[0]
        else:
            next_node = None
        
        self.navigator.append("exit intersection at " + curr_node)
        self.navigator.append("go straight")
        return prev_node, curr_node, next_node
    
    def compute_route_list(self):
        ''' Augments the route stored in self.route_graph'''
        #print("source=",source)
        #print("target=",target)
        #print("edges=",self.route_graph.edges.data())
        #print("nodes=",self.route_graph.nodes.data())
        #print(self.route_graph)
        
        curr_node = self.source
        prev_node = curr_node
        next_node = list(self.route_graph.successors(curr_node))[0]

        #reset route list
        self.route_list = []

        #print("curr_node",curr_node)
        #print("prev_node",prev_node)
        #print("next_node",next_node)
        self.navigator.append("go straight")
        while curr_node != self.target:
            xp,yp = self.get_coord(prev_node)
            xc,yc = self.get_coord(curr_node)
            xn,yn = self.get_coord(next_node)

            #print("from",curr_node,"(",xc,yc,")"," to ",next_node,"(",xn,yn,")")
            #print("edge: ",self.route_graph.get_edge_data(curr_node, next_node))
            #print("prev_node is",prev_node,"(",xp,yp,")")
            #print("*************************\n")
            
            curr_is_junction = curr_node in self.intersection_cen#len(adj_nodes) > 1
            next_is_intersection = next_node in self.intersection_cen#len(next_adj_nodes) > 1
            prev_is_intersection = prev_node in self.intersection_cen#len(prev_adj_nodes) > 1
            next_is_roundabout_enter = next_node in self.ra_enter
            curr_in_roundabout = curr_node in self.ra
            #print(f"CURR: {curr_node}, NEXT: {next_node}, PREV: {prev_node}")
            # ****** ROUNDABOUT NAVIGATION ******
            if next_is_roundabout_enter:
                if curr_node == "342":
                    self.route_list.append((xc,yc,np.rad2deg(np.arctan2(-1,0))))
                    dx = xc - xp
                    dy = yc - yp
                    self.route_list.append((xc,yc+0.3*dy,np.rad2deg(np.arctan2(-1,0))))
                else:
                    dx = xc-xp
                    dy = yc-yp
                    self.route_list.append((xc,yc,np.rad2deg(np.arctan2(dy,dx))))
                    # add a further node
                    dx = xc - xp
                    dy = yc - yp
                    self.route_list.append((xc+0.3*dx,yc+0.3*dy,np.rad2deg(np.arctan2(dy,dx))))
                # enter the roundabout
                self.navigator.append("enter roundabout at " + curr_node)
                prev_node, curr_node, next_node = self.roundabout_navigation(prev_node, curr_node, next_node)
                continue               
            elif next_is_intersection:
                dx = xc - xp
                dy = yc - yp
                self.route_list.append((xc,yc,np.rad2deg(np.arctan2(dy,dx))))
                # add a further node
                dx = xc - xp
                dy = yc - yp
                self.route_list.append((xc+0.3*dx,yc+0.3*dy,np.rad2deg(np.arctan2(dy,dx))))
                # enter the intersection
                self.navigator.append("enter intersection at " + curr_node)
                prev_node, curr_node, next_node = self.intersection_navigation(prev_node, curr_node, next_node)
                continue
            elif prev_is_intersection:
                # add a further node
                dx = xn - xc
                dy = yn - yc
                self.route_list.append((xc-0.3*dx,yc-0.3*dy,np.rad2deg(np.arctan2(dy,dx))))
                # and add the exit node
                dx = xn - xc
                dy = yn - yc
                self.route_list.append((xc,yc,np.rad2deg(np.arctan2(dy,dx))))
            else:
                dx = xn - xp
                dy = yn - yp
                self.route_list.append((xc,yc,np.rad2deg(np.arctan2(dy,dx))))
            
            prev_node = curr_node
            curr_node = next_node
            if curr_node != self.target:
                next_node = list(self.route_graph.successors(curr_node))[0]
            else:
                # You arrived at the END
                dx = xn - xp
                dy = yn - yp
                self.route_list.append((xn,yn,np.rad2deg(np.arctan2(dy,dx))))
                next_node = None
        
        self.navigator.append("stop")

    def compute_shortest_path(self, source=None, target=None, step_length=0.01):
        ''' Generates the shortest path between source and target nodes using Clothoid interpolation '''
        src = str(source) if source is not None else self.source
        tgt = str(target) if target is not None else self.target
        self.source = src
        self.target = tgt
        self.step_length = step_length
        route_nx = []

        # generate the shortest route between source and target      
        route_nx = list(nx.shortest_path(self.G, source=src, target=tgt)) 
        # generate a route subgraph       
        self.route_graph = nx.DiGraph() #reset the graph
        self.route_graph.add_nodes_from(route_nx)
        for i in range(len(route_nx)-1):
            self.route_graph.add_edges_from( [ (route_nx[i], route_nx[i+1], self.G.get_edge_data(route_nx[i],route_nx[i+1])) ] )         # augment route with intersections and roundabouts
        # expand route node and update navigation instructions
        self.compute_route_list()
        
        #self.print_navigation_instructions()
        # interpolate the route of nodes
        self.path = PathPlanning.interpolate_route(self.route_list, step_length)

        # self.augment_path()
        return self.path
    
    def augment_path(self, draw=True):

        self.path_stop_line_points = []
        self.path_stop_line_points_idx = []
        self.path_stop_line_types = []

        #get all the points the path intersects with the stop_line_points
        for i in range(len(self.stop_line_points)):
            p = self.stop_line_points[i]
            distances = np.linalg.norm(self.path - p, axis=1)
            index_min_dist = np.argmin(distances)
            min_dist = distances[index_min_dist]
            if min_dist < 0.05:
                self.path_stop_line_points.append(p)
                self.path_stop_line_points_idx.append(index_min_dist)
                self.path_stop_line_types.append(self.stop_line_types[i])
                if draw:
                    cv.circle(self.map, (m2pix(p[0]), m2pix(p[1])), 20, (0,255,0), 5)

    def generate_path_passing_through(self, list_of_nodes, step_length=0.01):
        """
        Extend the path generation from source-target to a sequence of nodes/locations
        """
        assert len(list_of_nodes) >= 2, "List of nodes must have at least 2 nodes"
        print("Generating path passing through: ", list_of_nodes)
        src = list_of_nodes[0]
        tgt = list_of_nodes[1]
        complete_path = self.compute_shortest_path(source=src, target=tgt, step_length=step_length)
        for i in range(1,len(list_of_nodes)-1):
            src = list_of_nodes[i]
            tgt = list_of_nodes[i+1]
            self.compute_shortest_path(source=src, target=tgt, step_length=step_length)
            #now the local path is computed in self.path
            #remove first element of self.path
            self.path = self.path[1:]
            #we need to add the local path to the complete path
            complete_path = np.concatenate((complete_path, self.path))
        self.path = complete_path
        self.augment_path()

    def get_path_ahead(self, index, look_ahead=100):
        assert index < len(self.path) and index >= 0
        return np.array(self.path[index:min(index + look_ahead, len(self.path)-1), :])

    def get_closest_stop_line(self, nx, ny, draw=False):
        """
        Returns the closest stop point to the given point
        """
        index_closest = np.argmin(np.hypot(nx - self.stop_points[:,0], ny - self.stop_points[:,1]))
        print(f'Closest stop point is {self.stop_points[index_closest, :]}, Point is {nx, ny}')
        #draw a circle around the closest stop point
        if draw: cv.circle(self.map, (m2pix(self.stop_points[index_closest, 0]), m2pix(self.stop_points[index_closest, 1])), 8, (0, 255, 0), 4)
        return self.stop_points[index_closest, 0], self.stop_points[index_closest, 1]

    def print_path_info(self):
        prev_state = None
        prev_next_state = None
        for i in range(len(self.path_data)-1):
            curr_state = self.path_data[i][0]
            next_state = self.path_data[i][1]
            if curr_state != prev_state or next_state != prev_next_state:
                print(f'{i}: {self.path_data[i]}')
            prev_state = curr_state
            prev_next_state = next_state

    def get_length(self, path=None):
        ''' Calculates the length of the trajectory '''
        if path is None:
            return 0
        length = 0
        for i in range(len(path)-1):
            x1,y1 = path[i]
            x2,y2 = path[i+1]
            length += np.hypot(x2-x1,y2-y1) 
        return length

    def get_coord(self, node):
        x = self.nodes_data[node]['x']
        y = self.nodes_data[node]['y']
        return x, y
    
    def get_path(self):
        return self.path
    
    def print_navigation_instructions(self):
        for i,instruction in enumerate(self.navigator):
            print(i+1,") ",instruction)
    
    @staticmethod
    def compute_path(xi, yi, thi, xf, yf, thf, step_length):
        clothoid_path = Clothoid.G1Hermite(xi, yi, thi, xf, yf, thf)
        length = clothoid_path.length
        [X,Y] = clothoid_path.SampleXY(int(length/step_length))
        return [X,Y]
    
    @staticmethod
    def interpolate_route(route, step_length):
        path_X = []
        path_Y = []

        # interpolate the route of nodes
        for i in range(len(route)-1):
            xc,yc,thc = route[i]
            xn,yn,thn = route[i+1]
            thc = np.deg2rad(thc)
            thn = np.deg2rad(thn)

            #print("from (",xc,yc,thc,") to (",xn,yn,thn,")\n")

            # Clothoid interpolation
            [X,Y] = PathPlanning.compute_path(xc, yc, thc, xn, yn, thn, step_length)

            for x,y in zip(X,Y):
                path_X.append(x)
                path_Y.append(y)
        
        # build array for cv.polylines
        path = []
        prev_x = 0.0
        prev_y = 0.0
        for i, (x,y) in enumerate(zip(path_X, path_Y)):
            if not (np.isclose(x,prev_x, rtol=1e-5) and np.isclose(y, prev_y, rtol=1e-5)):
                path.append([x,y])
            # else:
            #     print(f'Duplicate point: {x}, {y}, index {i}')
            prev_x = x
            prev_y = y
        
        path = np.array(path, dtype=np.float32)
        return path

    def draw_path(self):
        # print png image
        #map = cv.imread('Track.png')
        #map = cv.imread('src/models_pkg/track/materials/textures/2021_Medium.png')
        # get sizes
        #height, width, channels = self.map.shape
        #print(height, width)

        # draw nodes
        for node in self.list_of_nodes:
            x,y = self.get_coord(node)
            x = m2pix(x)
            y = m2pix(y)
            cv.circle(self.map, (x, y), 5, (0, 0, 255), -1)
            #add node number
            cv.putText(self.map, str(node), (x, y), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # draw edges
        for edge in self.list_of_edges:
            x1,y1 = self.get_coord(edge[0])
            x2,y2 = self.get_coord(edge[1])
            x1 = m2pix(x1)
            y1 = m2pix(y1)
            x2 = m2pix(x2)
            y2 = m2pix(y2)
            #cv.line(self.map, (x1, y1), (x2, y2), (0, 255, 255), 2)

        # draw all points in given path
        for point in self.route_list:
            x,y,_ = point
            x = m2pix(x)
            y = m2pix(y)
            cv.circle(self.map, (x, y), 5, (255, 0, 0), 1)

        # draw trajectory
        cv.polylines(self.map, [m2pix(self.path)], False, (200, 200, 0), thickness=4, lineType=cv.LINE_AA)

        # show windows
        cv.namedWindow('Path', cv.WINDOW_NORMAL)
        cv.resizeWindow('Path', 800, 800)
        cv.imshow('Path', self.map)
        # save current image
        # cv.imwrite('my_trajectory.png', self.map)
        cv.waitKey(1)