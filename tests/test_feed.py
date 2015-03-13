import unittest
from copy import copy

import pandas as pd 
import numpy as np
from pandas.util.testing import assert_frame_equal, assert_series_equal
from shapely.geometry import Point, LineString, mapping
from shapely.geometry import shape as sh_shape

from gtfs_tk.feed import *
from gtfs_tk.utils import *

# Load test feeds
cairns = Feed('data/cairns_gtfs.zip')
cairns_shapeless = Feed('data/cairns_gtfs.zip')
cairns_shapeless.shapes = None

class TestFeed(unittest.TestCase):

    def test_init(self):
        # Test distance units check
        self.assertRaises(AssertionError, Feed, 
          path='data/cairns_gtfs.zip', 
          original_units='bingo')
        # Test file checks
        feed = Feed('data/cairns_gtfs.zip')
        for f in REQUIRED_GTFS_FILES + ['calendar_dates', 'shapes']:
            self.assertIsInstance(getattr(feed, f), 
              pd.core.frame.DataFrame)
        for f in [f for f in OPTIONAL_GTFS_FILES 
          if f not in ['calendar_dates', 'shapes']]:
            self.assertIsNone(getattr(feed, f))

    def test_get_stops_stats_outer(self):
        feed = copy(cairns)
        st = pd.merge(feed.stop_times, 
          feed.trips[['trip_id', 'direction_id']])
        for split_directions in [True, False]:
            stops_stats = get_stops_stats(st, 
              split_directions=split_directions)
            # Should be a data frame
            self.assertIsInstance(stops_stats, pd.core.frame.DataFrame)
            # Should contain the correct columns
            expect_cols = set([
              'stop_id',
              'num_trips',
              'max_headway',
              'mean_headway',
              'start_time',
              'end_time',
              ])
            if split_directions:
                expect_cols.add('direction_id')
            self.assertEqual(set(stops_stats.columns), expect_cols)
            # Should contain the correct stops
            expect_stops = set(feed.stops['stop_id'].values)
            get_stops = set(stops_stats['stop_id'].values)
            self.assertEqual(get_stops, expect_stops)

    # def test_get_stops_time_series_outer(self):
    #     feed = copy(cairns)
    #     date = feed.get_dates()[0]
    #     ast = pd.merge(feed.get_trips(date), feed.stop_times)
    #     for split_directions in [True, False]:
    #         f = feed.get_stops_stats(date, 
    #           split_directions=split_directions)
    #         stops_ts = feed.get_stops_time_series(date, freq='1H',
    #           split_directions=split_directions) 
            
    #         # Should be a data frame
    #         self.assertIsInstance(stops_ts, pd.core.frame.DataFrame)
            
    #         # Should have the correct shape
    #         self.assertEqual(stops_ts.shape[0], 24)
    #         self.assertEqual(stops_ts.shape[1], f.shape[0])
            
    #         # Should have correct column names
    #         if split_directions:
    #             expect = ['indicator', 'stop_id', 'direction_id']
    #         else:
    #             expect = ['indicator', 'stop_id']
    #         self.assertEqual(stops_ts.columns.names, expect)

    #         # Each stop should have a correct total trip count
    #         if split_directions == False:
    #             astg = ast.groupby('stop_id')
    #             for stop in set(ast['stop_id'].values):
    #                 get = stops_ts['num_trips'][stop].sum() 
    #                 expect = astg.get_group(stop)['departure_time'].count()
    #                 self.assertEqual(get, expect)
        
    #     # None check
    #     date = '19000101'
    #     stops_ts = feed.get_stops_time_series(date, freq='1H',
    #       split_directions=split_directions) 
    #     self.assertIsNone(stops_ts)

    # Test route methods
    # ----------------------------------
    def test_fill_nan_route_short_names(self):
        feed = copy(cairns) # Has all non-nan route short names
        
        # Set some route short names to nan
        f = feed.routes
        g = f[f['route_short_name'].str.startswith('12')]
        g_indices = g.index.tolist()
        for i in g_indices:
            f['route_short_name'].iat[i] = np.nan
        
        # Fill nans
        feed.fill_nan_route_short_names('bingo')
        h = f[f['route_short_name'].str.startswith('bingo')]
        h_indices = h.index.tolist()
        
        # The indices we set to nan should equal the indices we filled
        self.assertEqual(h_indices, g_indices)

        # The fill values should be correct. Just check the numeric suffixes.
        get = [int(x.lstrip('bingo')) for x in h['route_short_name'].values]
        expect = list(range(len(h_indices)))
        self.assertEqual(get, expect)

    def test_get_routes(self):
        feed = copy(cairns)
        date = feed.get_dates()[0]
        f = feed.get_routes(date)
        # Should be a data frame
        self.assertIsInstance(f, pd.core.frame.DataFrame)
        # Should have the correct shape
        self.assertTrue(f.shape[0] <= feed.routes.shape[0])
        self.assertEqual(f.shape[1], feed.routes.shape[1])
        # Should have correct columns
        self.assertEqual(set(f.columns), set(feed.routes.columns))

        g = feed.get_routes(date, "07:30:00")
        # Should be a data frame
        self.assertIsInstance(g, pd.core.frame.DataFrame)
        # Should have the correct shape
        self.assertTrue(g.shape[0] <= f.shape[0])
        self.assertEqual(g.shape[1], f.shape[1])
        # Should have correct columns
        self.assertEqual(set(g.columns), set(feed.routes.columns))

    def test_get_routes_stats(self):
        feed = copy(cairns)
        date = feed.get_dates()[0]
        trips_stats = feed.get_trips_stats()
        f = pd.merge(trips_stats, feed.get_trips(date))
        for split_directions in [True, False]:
            rs = feed.get_routes_stats(trips_stats, date, 
              split_directions=split_directions)

            # Should be a data frame of the correct shape
            self.assertIsInstance(rs, pd.core.frame.DataFrame)
            if split_directions:
                f['tmp'] = f['route_id'] + '-' +\
                  f['direction_id'].map(str)
            else:
                f['tmp'] = f['route_id'].copy()
            expect_num_routes = len(f['tmp'].unique())
            self.assertEqual(rs.shape[0], expect_num_routes)

            # Should contain the correct columns
            expect_cols = set([
              'route_id',
              'num_trips',
              'start_time',
              'end_time',
              'max_headway',
              'mean_headway', 
              'service_duration', 
              'service_distance',
              'service_speed',              
              ])
            if split_directions:
                expect_cols.add('direction_id')
            self.assertEqual(set(rs.columns), expect_cols)

    def test_get_routes_time_series(self):
        feed = copy(cairns)
        date = feed.get_dates()[0]
        trips_stats = feed.get_trips_stats()
        ats = pd.merge(trips_stats, feed.get_trips(date))
        for split_directions in [True, False]:
            f = feed.get_routes_stats(trips_stats, date, 
              split_directions=split_directions)
            rts = feed.get_routes_time_series(trips_stats, date, 
              split_directions=split_directions, freq='1H')
            
            # Should be a data frame of the correct shape
            self.assertIsInstance(rts, pd.core.frame.DataFrame)
            self.assertEqual(rts.shape[0], 24)
            self.assertEqual(rts.shape[1], 5*f.shape[0])
            
            # Should have correct column names
            if split_directions:
                expect = ['indicator', 'route_id', 'direction_id']
            else:
                expect = ['indicator', 'route_id']
            self.assertEqual(rts.columns.names, expect)   
            
            # Each route have a correct service distance total
            if split_directions == False:
                atsg = ats.groupby('route_id')
                for route in ats['route_id'].values:
                    get = rts['service_distance'][route].sum() 
                    expect = atsg.get_group(route)['distance'].sum()
                    self.assertTrue(abs((get - expect)/expect) < 0.001)

        # None check
        date = '19000101'
        rts = feed.get_routes_time_series(trips_stats, date, 
          split_directions=split_directions, freq='1H')
        self.assertIsNone(rts)

    def test_agg_routes_time_series(self):
        feed = copy(cairns)
        date = feed.get_dates()[0]
        trips_stats = feed.get_trips_stats()
        for split_directions in [True, False]:
            rts = feed.get_routes_time_series(trips_stats, date, 
              split_directions=split_directions, freq='1H')
            arts = agg_routes_time_series(rts)
            if split_directions:
                num_cols = 2*len(rts.columns.levels[0])
                col_names = ['indicator', 'direction_id']
            else:
                num_cols = len(rts.columns.levels[0])
                col_names = [None]
            # Should be a data frame of the correct shape
            self.assertIsInstance(arts, pd.core.frame.DataFrame)
            self.assertEqual(arts.shape[0], 24)
            self.assertEqual(arts.shape[1], num_cols)
            # Should have correct column names
            self.assertEqual(arts.columns.names, col_names)   

    def test_get_route_timetable(self):
        feed = copy(cairns)
        route = feed.routes['route_id'].values[0]
        date = feed.get_dates()[0]
        f = feed.get_route_timetable(route, date)
        # Should be a data frame 
        self.assertIsInstance(f, pd.core.frame.DataFrame)
        # Should have the correct columns
        expect_cols = set(feed.trips.columns) |\
          set(feed.stop_times.columns)
        self.assertEqual(set(f.columns), expect_cols)

    # Test trip methods
    # ----------------------------------
    def test_is_active(self):
        feed = copy(cairns)
        trip = 'CNS2014-CNS_MUL-Weekday-00-4165878'
        date1 = '20140526'
        date2 = '20120322'
        self.assertTrue(feed.is_active_trip(trip, date1))
        self.assertFalse(feed.is_active_trip(trip, date2))

        trip = 'CNS2014-CNS_MUL-Sunday-00-4165971'
        date1 = '20140601'
        date2 = '20120602'
        self.assertTrue(feed.is_active_trip(trip, date1))
        self.assertFalse(feed.is_active_trip(trip, date2))

        feed = Feed('data/portland_gtfs.zip')
        trip = '4526377'
        date1 = '20140518'
        date2 = '20120517'
        self.assertTrue(feed.is_active_trip(trip, date1))
        self.assertFalse(feed.is_active_trip(trip, date2))

    def test_get_trips(self):
        feed = copy(cairns)
        date = feed.get_dates()[0]
        f = feed.get_trips(date)
        # Should be a data frame
        self.assertIsInstance(f, pd.core.frame.DataFrame)
        # Should have the correct shape
        self.assertTrue(f.shape[0] <= feed.trips.shape[0])
        self.assertEqual(f.shape[1], feed.trips.shape[1])
        # Should have correct columns
        self.assertEqual(set(f.columns), set(feed.trips.columns))

        g = feed.get_trips(date, "07:30:00")
        # Should be a data frame
        self.assertIsInstance(g, pd.core.frame.DataFrame)
        # Should have the correct shape
        self.assertTrue(g.shape[0] <= f.shape[0])
        self.assertEqual(g.shape[1], f.shape[1])
        # Should have correct columns
        self.assertEqual(set(g.columns), set(feed.trips.columns))

    def test_get_trips_locations(self):
        feed = copy(cairns)
        trips_stats = feed.get_trips_stats()
        feed.add_dist_to_stop_times(trips_stats)
        linestring_by_shape = feed.get_linestring_by_shape(use_utm=False)
        date = feed.get_dates()[0]
        timestrs = ['08:00:00']
        f = feed.get_trips_locations(linestring_by_shape, date, timestrs)
        g = feed.get_trips(date, timestrs[0])
        # Should be a data frame
        self.assertIsInstance(f, pd.core.frame.DataFrame)
        # Should have the correct number of rows
        self.assertEqual(f.shape[0], g.shape[0])
        # Should have the correct columns
        get_cols = set(f.columns)
        expect_cols = set(list(g.columns) + ['time', 'rel_dist', 'lon', 'lat'])
        self.assertEqual(get_cols, expect_cols)
    
    def test_get_trips_activity(self):
        feed = copy(cairns)
        dates = feed.get_first_week()
        trips_activity = feed.get_trips_activity(dates)
        # Should be a data frame
        self.assertIsInstance(trips_activity, pd.core.frame.DataFrame)
        # Should have the correct shape
        self.assertEqual(trips_activity.shape[0], feed.trips.shape[0])
        self.assertEqual(trips_activity.shape[1], len(dates) + 3)
        # Date columns should contain only zeros and ones
        self.assertEqual(set(trips_activity[dates].values.flatten()), {0, 1})

    def test_get_trips_stats(self):
        feed = copy(cairns)
        trips_stats = feed.get_trips_stats()
        
        # Should be a data frame with the correct number of rows
        self.assertIsInstance(trips_stats, pd.core.frame.DataFrame)
        self.assertEqual(trips_stats.shape[0], feed.trips.shape[0])
        
        # Should contain the correct columns
        expect_cols = set([
          'trip_id',
          'direction_id',
          'route_id',
          'shape_id',
          'start_time', 
          'end_time',
          'duration',
          'start_stop_id',
          'end_stop_id',
          'num_stops',
          'distance',
          ])
        self.assertEqual(set(trips_stats.columns), expect_cols)
        
        # Shapeless feeds should have null entries for distance column
        feed2 = cairns_shapeless
        trips_stats = feed2.get_trips_stats()
        self.assertEqual(len(trips_stats['distance'].unique()), 1)
        self.assertTrue(np.isnan(trips_stats['distance'].unique()[0]))   
        
        # Should contain the correct trips
        get_trips = set(trips_stats['trip_id'].values)
        expect_trips = set(feed.trips['trip_id'].values)
        self.assertEqual(get_trips, expect_trips)
    
    # Test stop methods
    # ----------------------------------
    def test_get_stops(self):
        feed = copy(cairns)
        date = feed.get_dates()[0]
        f = feed.get_stops(date)
        # Should be a data frame
        self.assertIsInstance(f, pd.core.frame.DataFrame)
        # Should have the correct shape
        self.assertTrue(f.shape[0] <= feed.stops.shape[0])
        self.assertEqual(f.shape[1], feed.stops.shape[1])
        # Should have correct columns
        self.assertEqual(set(f.columns), set(feed.stops.columns))

    def test_get_point_by_stop(self):
        feed = copy(cairns)
        point_by_stop = feed.get_point_by_stop()
        # Should be a dictionary
        self.assertIsInstance(point_by_stop, dict)
        # The first element should be a Shapely point
        self.assertIsInstance(list(point_by_stop.values())[0], Point)
        # Should include all stops
        self.assertEqual(len(point_by_stop), feed.stops.shape[0])

    def test_get_stops_activity(self):
        feed = copy(cairns)
        dates = feed.get_first_week()
        stops_activity = feed.get_stops_activity(dates)
        # Should be a data frame
        self.assertIsInstance(stops_activity, pd.core.frame.DataFrame)
        # Should have the correct shape
        self.assertEqual(stops_activity.shape[0], feed.stops.shape[0])
        self.assertEqual(stops_activity.shape[1], len(dates) + 1)
        # Date columns should contain only zeros and ones
        self.assertEqual(set(stops_activity[dates].values.flatten()), {0, 1})

    def test_get_stops_stats(self):
        feed = copy(cairns)
        date = feed.get_dates()[0]
        stops_stats = feed.get_stops_stats(date)
        # Should be a data frame
        self.assertIsInstance(stops_stats, pd.core.frame.DataFrame)
        # Should contain the correct stops
        get_stops = set(stops_stats['stop_id'].values)
        f = feed.get_stops(date)
        expect_stops = set(f['stop_id'].values)
        self.assertEqual(get_stops, expect_stops)

    def test_get_stops_time_series(self):
        feed = copy(cairns)
        date = feed.get_dates()[0]
        ast = pd.merge(feed.get_trips(date), feed.stop_times)
        for split_directions in [True, False]:
            f = feed.get_stops_stats(date, 
              split_directions=split_directions)
            stops_ts = feed.get_stops_time_series(date, freq='1H',
              split_directions=split_directions) 
            
            # Should be a data frame
            self.assertIsInstance(stops_ts, pd.core.frame.DataFrame)
            
            # Should have the correct shape
            self.assertEqual(stops_ts.shape[0], 24)
            self.assertEqual(stops_ts.shape[1], f.shape[0])
            
            # Should have correct column names
            if split_directions:
                expect = ['indicator', 'stop_id', 'direction_id']
            else:
                expect = ['indicator', 'stop_id']
            self.assertEqual(stops_ts.columns.names, expect)

            # Each stop should have a correct total trip count
            if split_directions == False:
                astg = ast.groupby('stop_id')
                for stop in set(ast['stop_id'].values):
                    get = stops_ts['num_trips'][stop].sum() 
                    expect = astg.get_group(stop)['departure_time'].count()
                    self.assertEqual(get, expect)
        
        # None check
        date = '19000101'
        stops_ts = feed.get_stops_time_series(date, freq='1H',
          split_directions=split_directions) 
        self.assertIsNone(stops_ts)

    def test_get_stop_timetable(self):
        feed = copy(cairns)
        stop = feed.stops['stop_id'].values[0]
        date = feed.get_dates()[0]
        f = feed.get_stop_timetable(stop, date)
        # Should be a data frame 
        self.assertIsInstance(f, pd.core.frame.DataFrame)
        # Should have the correct columns
        expect_cols = set(feed.trips.columns) |\
          set(feed.stop_times.columns)
        self.assertEqual(set(f.columns), expect_cols)    

    # Test shape methods
    # ----------------------------------
    def test_get_linestring_by_shape(self):
        feed = copy(cairns)
        linestring_by_shape = feed.get_linestring_by_shape()
        # Should be a dictionary
        self.assertIsInstance(linestring_by_shape, dict)
        # The first element should be a Shapely linestring
        self.assertIsInstance(list(linestring_by_shape.values())[0], 
          LineString)
        # Should contain all shapes
        self.assertEqual(len(linestring_by_shape), 
          feed.shapes.groupby('shape_id').first().shape[0])
        # Should be None if feed.shapes is None
        feed2 = cairns_shapeless
        self.assertIsNone(feed2.get_linestring_by_shape())

    def test_add_dist_to_shapes(self):
        feed = copy(cairns)
        s1 = feed.shapes.copy()
        feed.add_dist_to_shapes()
        s2 = feed.shapes
        # Check that colums of st2 equal the columns of st1 plus
        # a shape_dist_traveled column
        cols1 = list(s1.columns.values) + ['shape_dist_traveled']
        cols2 = list(s2.columns.values)
        self.assertEqual(set(cols1), set(cols2))

        # Check that within each trip the shape_dist_traveled column 
        # is monotonically increasing
        for name, group in s2.groupby('shape_id'):
            sdt = list(group['shape_dist_traveled'].values)
            self.assertEqual(sdt, sorted(sdt))

    def test_get_shapes_geojson(self):
        feed = copy(cairns)
        collection = json.loads(feed.get_shapes_geojson())
        linestring_by_shape = feed.get_linestring_by_shape(use_utm=False)
        for f in collection['features']:
            shape = f['properties']['shape_id']
            geom = sh_shape(f['geometry'])
            self.assertTrue(geom.equals(linestring_by_shape[shape]))

    # Test stop time methods
    # ----------------------------------
    def test_get_stop_times(self):
        feed = copy(cairns)
        date = feed.get_dates()[0]
        f = feed.get_stop_times(date)
        # Should be a data frame
        self.assertIsInstance(f, pd.core.frame.DataFrame)
        # Should have a reasonable shape
        self.assertTrue(f.shape[0] <= feed.stop_times.shape[0])
        # Should have correct columns
        self.assertEqual(set(f.columns), set(feed.stop_times.columns))

    def test_add_dist_to_stop_times(self):
        feed = copy(cairns)
        st1 = feed.stop_times.copy()
        trips_stats = feed.get_trips_stats()
        feed.add_dist_to_stop_times(trips_stats)
        st2 = feed.stop_times

        # Check that colums of st2 equal the columns of st1 plus
        # a shape_dist_traveled column
        cols1 = list(st1.columns.values) + ['shape_dist_traveled']
        cols2 = list(st2.columns.values)
        self.assertEqual(set(cols1), set(cols2))

        # Check that within each trip the shape_dist_traveled column 
        # is monotonically increasing
        for trip, group in st2.groupby('trip_id'):
            group = group.sort('stop_sequence')
            sdt = list(group['shape_dist_traveled'].values)
            print('-'*40)
            print('trip', trip, sdt)
            self.assertEqual(sdt, sorted(sdt))

    # Test other methods
    # ----------------------------------
    def test_get_dates(self):
        feed = copy(cairns)
        for as_date_obj in [True, False]:
            dates = feed.get_dates(as_date_obj=as_date_obj)
            d1 = '20140526'
            d2 = '20141228'
            if as_date_obj:
                d1 = utils.datestr_to_date(d1)
                d2 = utils.datestr_to_date(d2)
                self.assertEqual(len(dates), (d2 - d1).days + 1)
            self.assertEqual(dates[0], d1)
            self.assertEqual(dates[-1], d2)

    def test_get_first_week(self):
        feed = copy(cairns)
        dates = feed.get_first_week()
        d1 = '20140526'
        d2 = '20140601'
        self.assertEqual(dates[0], d1)
        self.assertEqual(dates[-1], d2)
        self.assertEqual(len(dates), 7)

    def test_get_busiest_date_of_first_week(self):
        feed = copy(cairns)
        dates = feed.get_first_week()
        date = feed.get_busiest_date_of_first_week()
        # Busiest day should lie in first week
        self.assertTrue(date in dates)
    
    def test_export(self):
        feed1 = copy(cairns)
        # Export feed1, import it as feed2, and then test that the
        # attributes of the two feeds are equal.
        path = 'data/test_gtfs.zip'
        feed1.export(path)
        feed2 = Feed(path)
        names = REQUIRED_GTFS_FILES + OPTIONAL_GTFS_FILES
        for name in names:
            attr1 = getattr(feed1, name)
            attr2 = getattr(feed2, name)
            print(attr1)
            if attr1 is not None:
                assert_frame_equal(attr1, attr2)
            else:
                self.assertIsNone(attr2)


if __name__ == '__main__':
    unittest.main()