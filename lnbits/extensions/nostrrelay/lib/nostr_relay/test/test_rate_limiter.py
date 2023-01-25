import unittest
import time
from nostr_relay import rate_limiter


class RateLimiterTests(unittest.TestCase):
    def test_parse_options(self):
        """
        Test option parsing
        """
        limiter = rate_limiter.RateLimiter()
        assert limiter.parse_option('5/s') == [(1.0, 5.0)]
        assert limiter.parse_option('50/HOUR,,,;') == [(3600.0, 50.0)]
        assert limiter.parse_option('100/h,1/sec,10/minute') == [(3600.0, 100.0), (60.0, 10.0), (1.0, 1.0)]
        with self.assertRaises(ValueError):
            limiter.parse_option('1000/year')

    def test_limits(self):
        """
        Test that limits work
        """
        limiter = rate_limiter.RateLimiter({'global': {'EVENT': '10/second,11/minute'}})
        message = ['EVENT', {}]
        ip_address = '127.0.0.1'
        for i in range(10):
            assert not limiter.is_limited(ip_address, message)
        assert limiter.is_limited(ip_address, message)
        time.sleep(1)
        assert not limiter.is_limited(ip_address, message)

        assert limiter.is_limited(ip_address, message)

    def test_resetting_limits(self):
        """
        Test that the recent timestamp queue doesn't expand infinitely
        """
        limiter = rate_limiter.RateLimiter({'global': {'EVENT': '5/second'}})
        message = ['EVENT', {}]
        ip_address = '127.0.0.1'
        for i in range(5):
            assert not limiter.is_limited(ip_address, message)
        assert len(limiter.recent_commands['global']['EVENT']) == 5

        time.sleep(1)
        assert not limiter.is_limited(ip_address, message)
        assert len(limiter.recent_commands['global']['EVENT']) == 1

    def test_ip_limits(self):
        """
        Test that the ip address and global limits work together
        """
        limiter = rate_limiter.RateLimiter(
            {'global': {
                'EVENT': '8/second'
                }, 
            'ip': {
                'EVENT': '5/second',
                'CLOSE': '10/s',
            }
        })
        message = ['EVENT', {}]
        ip_address = '127.0.0.1'

        for i in range(5):
            assert not limiter.is_limited(ip_address, message)
        assert limiter.is_limited(ip_address, message)
        assert not limiter.is_limited('1.1.1.1', message)
        assert not limiter.is_limited('1.1.1.1', message)
        assert limiter.is_limited('1.1.1.1', message)
        assert limiter.is_limited(ip_address, message)
        return limiter

    def test_get_limiter(self):
        """
        Test that we get a valid limiter
        """
        limiter = rate_limiter.get_rate_limiter({})
        assert not limiter.is_limited('test', 'blah')
        limiter = rate_limiter.get_rate_limiter({'rate_limits': {'global': {'EVENT': '1/hr'}}})
        assert not limiter.is_limited('test', 'blah')
        assert not limiter.is_limited('test', ['EVENT', {}])
        assert limiter.is_limited('test', ['EVENT', {}])


    def test_cleanup(self):
        limiter = self.test_ip_limits()
        limiter.cleanup()

        assert limiter.recent_commands[b'\x7f\x00\x00\x01']
        time.sleep(1)
        limiter.cleanup()
        assert not limiter.recent_commands[b'\x7f\x00\x00\x01']

        limiter = rate_limiter.get_rate_limiter({"rate_limits": {"global": {"EVENT": "1/s"}}})
        limiter.cleanup()
        assert not limiter.recent_commands

    def test_ip_exempt(self):
        limiter = rate_limiter.RateLimiter({
            'global': {'EVENT': '5/second,11/minute'}, 
            '1.1.1.1': {'EVENT': '10/s'},
            '8.8.8.8': {'EVENT': '-1/s'}
        })
        message = ['EVENT', {}]
        ip_address = '127.0.0.1'

        for i in range(5):
            assert not limiter.is_limited(ip_address, message)
        assert limiter.is_limited(ip_address, message)

        ip_address = '1.1.1.1'

        for i in range(10):
            assert not limiter.is_limited(ip_address, message)
        assert limiter.is_limited(ip_address, message)

        for i in range(12):
            assert not limiter.is_limited('8.8.8.8', message)

    def test_no_rules(self):
        limiter = rate_limiter.RateLimiter()
        message = ['EVENT', {}]
        ip_address = '127.0.0.1'
        assert not limiter.is_limited(ip_address, message)



if __name__ == "__main__":
    unittest.main()
