/*!
 * Quasar Framework v1.9.7
 * (c) 2015-present Razvan Stoenescu
 * Released under the MIT License.
 */

(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory(require('vue')) :
  typeof define === 'function' && define.amd ? define(['vue'], factory) :
  (global = global || self, global.Quasar = factory(global.Vue));
}(this, (function (Vue) { 'use strict';

  if (Vue === void 0) {
    console.error('[ Quasar ] Vue is required to run. Please add a script tag for it before loading Quasar.')
    return
  }
  Vue = Vue && Vue.hasOwnProperty('default') ? Vue['default'] : Vue;

  var version = "1.9.7";

  /* eslint-disable no-useless-escape */

  var isSSR = typeof window === 'undefined';
  var fromSSR = false;
  var onSSR = isSSR;

  var iosEmulated = false;
  var iosCorrection;

  function getMatch (userAgent, platformMatch) {
    var match = /(edge|edga|edgios)\/([\w.]+)/.exec(userAgent) ||
      /(opr)[\/]([\w.]+)/.exec(userAgent) ||
      /(vivaldi)[\/]([\w.]+)/.exec(userAgent) ||
      /(chrome|crios)[\/]([\w.]+)/.exec(userAgent) ||
      /(iemobile)[\/]([\w.]+)/.exec(userAgent) ||
      /(version)(applewebkit)[\/]([\w.]+).*(safari)[\/]([\w.]+)/.exec(userAgent) ||
      /(webkit)[\/]([\w.]+).*(version)[\/]([\w.]+).*(safari)[\/]([\w.]+)/.exec(userAgent) ||
      /(firefox|fxios)[\/]([\w.]+)/.exec(userAgent) ||
      /(webkit)[\/]([\w.]+)/.exec(userAgent) ||
      /(opera)(?:.*version|)[\/]([\w.]+)/.exec(userAgent) ||
      /(msie) ([\w.]+)/.exec(userAgent) ||
      (userAgent.indexOf('trident') >= 0 && /(rv)(?::| )([\w.]+)/.exec(userAgent)) ||
      (userAgent.indexOf('compatible') < 0 && /(mozilla)(?:.*? rv:([\w.]+)|)/.exec(userAgent)) ||
      [];

    return {
      browser: match[5] || match[3] || match[1] || '',
      version: match[2] || match[4] || '0',
      versionNumber: match[4] || match[2] || '0',
      platform: platformMatch[0] || ''
    }
  }

  function getPlatformMatch (userAgent) {
    return /(ipad)/.exec(userAgent) ||
      /(ipod)/.exec(userAgent) ||
      /(windows phone)/.exec(userAgent) ||
      /(iphone)/.exec(userAgent) ||
      /(kindle)/.exec(userAgent) ||
      /(silk)/.exec(userAgent) ||
      /(android)/.exec(userAgent) ||
      /(win)/.exec(userAgent) ||
      /(mac)/.exec(userAgent) ||
      /(linux)/.exec(userAgent) ||
      /(cros)/.exec(userAgent) ||
      /(playbook)/.exec(userAgent) ||
      /(bb)/.exec(userAgent) ||
      /(blackberry)/.exec(userAgent) ||
      []
  }

  var hasTouch = isSSR === false
    ? 'ontouchstart' in window || window.navigator.maxTouchPoints > 0
    : false;

  function applyIosCorrection (is) {
    var obj;

    iosCorrection = { is: Object.assign({}, is) };

    delete is.mac;
    delete is.desktop;

    var platform = Math.min(window.innerHeight, window.innerWidth) > 414
      ? 'ipad'
      : 'iphone';

    Object.assign(is, ( obj = {
      mobile: true,
      ios: true,
      platform: platform
    }, obj[ platform ] = true, obj ));
  }

  function getPlatform (userAgent) {
    var
      platformMatch = getPlatformMatch(userAgent),
      matched = getMatch(userAgent, platformMatch),
      browser = {};

    if (matched.browser) {
      browser[matched.browser] = true;
      browser.version = matched.version;
      browser.versionNumber = parseInt(matched.versionNumber, 10);
    }

    if (matched.platform) {
      browser[matched.platform] = true;
    }

    var knownMobiles = browser.android ||
      browser.ios ||
      browser.bb ||
      browser.blackberry ||
      browser.ipad ||
      browser.iphone ||
      browser.ipod ||
      browser.kindle ||
      browser.playbook ||
      browser.silk ||
      browser['windows phone'];

    // These are all considered mobile platforms, meaning they run a mobile browser
    if (knownMobiles === true || userAgent.indexOf('mobile') > -1) {
      browser.mobile = true;

      if (browser.edga || browser.edgios) {
        browser.edge = true;
        matched.browser = 'edge';
      }
      else if (browser.crios) {
        browser.chrome = true;
        matched.browser = 'chrome';
      }
      else if (browser.fxios) {
        browser.firefox = true;
        matched.browser = 'firefox';
      }
    }
    // If it's not mobile we should consider it's desktop platform, meaning it runs a desktop browser
    // It's a workaround for anonymized user agents
    // (browser.cros || browser.mac || browser.linux || browser.win)
    else {
      browser.desktop = true;
    }

    // Set iOS if on iPod, iPad or iPhone
    if (browser.ipod || browser.ipad || browser.iphone) {
      browser.ios = true;
    }

    if (browser['windows phone']) {
      browser.winphone = true;
      delete browser['windows phone'];
    }

    // Chrome, Opera 15+, Vivaldi and Safari are webkit based browsers
    if (
      browser.chrome ||
      browser.opr ||
      browser.safari ||
      browser.vivaldi ||
      // we expect unknown, non iOS mobile browsers to be webkit based
      (
        browser.mobile === true &&
        browser.ios !== true &&
        knownMobiles !== true
      )
    ) {
      browser.webkit = true;
    }

    // IE11 has a new token so we will assign it msie to avoid breaking changes
    if (browser.rv || browser.iemobile) {
      matched.browser = 'ie';
      browser.ie = true;
    }

    // Blackberry browsers are marked as Safari on BlackBerry
    if (browser.safari && browser.blackberry || browser.bb) {
      matched.browser = 'blackberry';
      browser.blackberry = true;
    }

    // Playbook browsers are marked as Safari on Playbook
    if (browser.safari && browser.playbook) {
      matched.browser = 'playbook';
      browser.playbook = true;
    }

    // Opera 15+ are identified as opr
    if (browser.opr) {
      matched.browser = 'opera';
      browser.opera = true;
    }

    // Stock Android browsers are marked as Safari on Android.
    if (browser.safari && browser.android) {
      matched.browser = 'android';
      browser.android = true;
    }

    // Kindle browsers are marked as Safari on Kindle
    if (browser.safari && browser.kindle) {
      matched.browser = 'kindle';
      browser.kindle = true;
    }

    // Kindle Silk browsers are marked as Safari on Kindle
    if (browser.safari && browser.silk) {
      matched.browser = 'silk';
      browser.silk = true;
    }

    if (browser.vivaldi) {
      matched.browser = 'vivaldi';
      browser.vivaldi = true;
    }

    // Assign the name and platform variable
    browser.name = matched.browser;
    browser.platform = matched.platform;

    if (isSSR === false) {
      if (userAgent.indexOf('electron') > -1) {
        browser.electron = true;
      }
      else if (document.location.href.indexOf('-extension://') > -1) {
        browser.bex = true;
      }
      else if (window.Capacitor !== void 0) {
        browser.capacitor = true;
        browser.nativeMobile = true;
        browser.nativeMobileWrapper = 'capacitor';
      }
      else if (window._cordovaNative !== void 0 || window.cordova !== void 0) {
        browser.cordova = true;
        browser.nativeMobile = true;
        browser.nativeMobileWrapper = 'cordova';
      }
      else if (
        hasTouch === true &&
        browser.desktop === true &&
        browser.mac === true &&
        browser.safari === true
      ) {
        /*
         * Correction needed for iOS since the default
         * setting on iPad is to request desktop view; if we have
         * touch support and the user agent says it's a
         * desktop, we infer that it's an iPhone/iPad with desktop view
         * so we must fix the false positives
         */
        applyIosCorrection(browser);
      }

      fromSSR = browser.nativeMobile === void 0 &&
        browser.electron === void 0 &&
        !!document.querySelector('[data-server-rendered]');

      if (fromSSR === true) {
        onSSR = true;
      }
    }

    return browser
  }

  var userAgent = isSSR === false
    ? (navigator.userAgent || navigator.vendor || window.opera).toLowerCase()
    : '';

  var ssrClient = {
    has: {
      touch: false,
      webStorage: false
    },
    within: { iframe: false }
  };

  // We export "client" for hydration error-free parts,
  // like touch directives who do not (and must NOT) wait
  // for the client takeover;
  // Do NOT import this directly in your app, unless you really know
  // what you are doing.
  var client = isSSR === false
    ? {
      userAgent: userAgent,
      is: getPlatform(userAgent),
      has: {
        touch: hasTouch,
        webStorage: (function () {
          try {
            if (window.localStorage) {
              return true
            }
          }
          catch (e) {}
          return false
        })()
      },
      within: {
        iframe: window.self !== window.top
      }
    }
    : ssrClient;

  var Platform = {
    install: function install ($q, queues) {
      var this$1 = this;

      if (isSSR === true) {
        // we're on server-side, so we push
        // to the server queue instead of
        // applying directly
        queues.server.push(function (q, ctx) {
          q.platform = this$1.parseSSR(ctx.ssr);
        });
      }
      else if (fromSSR === true) {
        // must match with server-side before
        // client taking over in order to prevent
        // hydration errors
        Object.assign(this, client, iosCorrection, ssrClient);

        // takeover should increase accuracy for
        // the rest of the props; we also avoid
        // hydration errors
        queues.takeover.push(function (q) {
          onSSR = fromSSR = false;
          Object.assign(q.platform, client);
          iosCorrection = void 0;
        });

        // we need to make platform reactive
        // for the takeover phase
        Vue.util.defineReactive($q, 'platform', this);
      }
      else {
        // we don't have any business with SSR, so
        // directly applying...
        Object.assign(this, client);
        $q.platform = this;
      }
    }
  };

  if (isSSR === true) {
    Platform.parseSSR = function (/* ssrContext */ ssr) {
      var userAgent = (ssr.req.headers['user-agent'] || ssr.req.headers['User-Agent'] || '').toLowerCase();
      return Object.assign({}, client,
        {userAgent: userAgent,
        is: getPlatform(userAgent)})
    };
  }
  else {
    iosEmulated = client.is.ios === true &&
      window.navigator.vendor.toLowerCase().indexOf('apple') === -1;
  }

  var listenOpts = {
    hasPassive: false,
    passiveCapture: true,
    notPassiveCapture: true
  };

  try {
    var opts = Object.defineProperty({}, 'passive', {
      get: function get () {
        Object.assign(listenOpts, {
          hasPassive: true,
          passive: { passive: true },
          notPassive: { passive: false },
          passiveCapture: { passive: true, capture: true },
          notPassiveCapture: { passive: false, capture: true }
        });
      }
    });
    window.addEventListener('qtest', null, opts);
    window.removeEventListener('qtest', null, opts);
  }
  catch (e) {}

  function noop () {}

  function leftClick (e) {
    return e.button === 0
  }

  function middleClick (e) {
    return e.button === 1
  }

  function rightClick (e) {
    return e.button === 2
  }

  function position (e) {
    if (e.touches && e.touches[0]) {
      e = e.touches[0];
    }
    else if (e.changedTouches && e.changedTouches[0]) {
      e = e.changedTouches[0];
    }
    else if (e.targetTouches && e.targetTouches[0]) {
      e = e.targetTouches[0];
    }

    return {
      top: e.clientY,
      left: e.clientX
    }
  }

  function getEventPath (e) {
    if (e.path) {
      return e.path
    }
    if (e.composedPath) {
      return e.composedPath()
    }

    var path = [];
    var el = e.target;

    while (el) {
      path.push(el);

      if (el.tagName === 'HTML') {
        path.push(document);
        path.push(window);
        return path
      }

      el = el.parentElement;
    }
  }

  // Reasonable defaults
  var
    LINE_HEIGHT = 40,
    PAGE_HEIGHT = 800;

  function getMouseWheelDistance (e) {
    var assign;

    var x = e.deltaX, y = e.deltaY;

    if ((x || y) && e.deltaMode) {
      var multiplier = e.deltaMode === 1 ? LINE_HEIGHT : PAGE_HEIGHT;
      x *= multiplier;
      y *= multiplier;
    }

    if (e.shiftKey && !x) {
      (assign = [x, y], y = assign[0], x = assign[1]);
    }

    return { x: x, y: y }
  }

  function stop (e) {
    e.stopPropagation();
  }

  function prevent (e) {
    e.cancelable !== false && e.preventDefault();
  }

  function stopAndPrevent (e) {
    e.cancelable !== false && e.preventDefault();
    e.stopPropagation();
  }

  function preventDraggable (el, status) {
    if (el === void 0 || (status === true && el.__dragPrevented === true)) {
      return
    }

    var fn = status === true
      ? function (el) {
        el.__dragPrevented = true;
        el.addEventListener('dragstart', prevent, listenOpts.notPassiveCapture);
      }
      : function (el) {
        delete el.__dragPrevented;
        el.removeEventListener('dragstart', prevent, listenOpts.notPassiveCapture);
      };

    el.querySelectorAll('a, img').forEach(fn);
  }

  function create (name, ref) {
    if ( ref === void 0 ) ref = {};
    var bubbles = ref.bubbles; if ( bubbles === void 0 ) bubbles = false;
    var cancelable = ref.cancelable; if ( cancelable === void 0 ) cancelable = false;

    try {
      return new Event(name, { bubbles: bubbles, cancelable: cancelable })
    }
    catch (e) {
      // IE doesn't support `new Event()`, so...
      var evt = document.createEvent('Event');
      evt.initEvent(name, bubbles, cancelable);
      return evt
    }
  }

  /*
   * also update /types/utils/event.d.ts
   */

  var event = {
    listenOpts: listenOpts,
    leftClick: leftClick,
    middleClick: middleClick,
    rightClick: rightClick,
    position: position,
    getEventPath: getEventPath,
    getMouseWheelDistance: getMouseWheelDistance,
    stop: stop,
    prevent: prevent,
    stopAndPrevent: stopAndPrevent,
    preventDraggable: preventDraggable,
    create: create
  };

  function debounce (fn, wait, immediate) {
    if ( wait === void 0 ) wait = 250;

    var timeout;

    function debounced (/* ...args */) {
      var this$1 = this;

      var args = arguments;

      var later = function () {
        timeout = void 0;
        if (immediate !== true) {
          fn.apply(this$1, args);
        }
      };

      clearTimeout(timeout);
      if (immediate === true && timeout === void 0) {
        fn.apply(this, args);
      }
      timeout = setTimeout(later, wait);
    }

    debounced.cancel = function () {
      clearTimeout(timeout);
    };

    return debounced
  }

  var SIZE_LIST = ['sm', 'md', 'lg', 'xl'];
  var passive = listenOpts.passive;

  var Screen = {
    width: 0,
    height: 0,

    name: 'xs',

    sizes: {
      sm: 600,
      md: 1024,
      lg: 1440,
      xl: 1920
    },

    lt: {
      sm: true,
      md: true,
      lg: true,
      xl: true
    },
    gt: {
      xs: false,
      sm: false,
      md: false,
      lg: false
    },
    xs: true,
    sm: false,
    md: false,
    lg: false,
    xl: false,

    setSizes: noop,
    setDebounce: noop,

    install: function install ($q, queues, cfg) {
      var this$1 = this;

      if (isSSR === true) {
        $q.screen = this;
        return
      }

      var classes = cfg.screen !== void 0 && cfg.screen.bodyClasses === true;

      var update = function (force) {
        var
          w = window.innerWidth,
          h = window.innerHeight;

        if (h !== this$1.height) {
          this$1.height = h;
        }

        if (w !== this$1.width) {
          this$1.width = w;
        }
        else if (force !== true) {
          return
        }

        var s = this$1.sizes;

        this$1.gt.xs = w >= s.sm;
        this$1.gt.sm = w >= s.md;
        this$1.gt.md = w >= s.lg;
        this$1.gt.lg = w >= s.xl;
        this$1.lt.sm = w < s.sm;
        this$1.lt.md = w < s.md;
        this$1.lt.lg = w < s.lg;
        this$1.lt.xl = w < s.xl;
        this$1.xs = this$1.lt.sm;
        this$1.sm = this$1.gt.xs === true && this$1.lt.md === true;
        this$1.md = this$1.gt.sm === true && this$1.lt.lg === true;
        this$1.lg = this$1.gt.md === true && this$1.lt.xl === true;
        this$1.xl = this$1.gt.lg;

        s = (this$1.xs === true && 'xs') ||
          (this$1.sm === true && 'sm') ||
          (this$1.md === true && 'md') ||
          (this$1.lg === true && 'lg') ||
          'xl';

        if (s !== this$1.name) {
          if (classes === true) {
            document.body.classList.remove(("screen--" + (this$1.name)));
            document.body.classList.add(("screen--" + s));
          }
          this$1.name = s;
        }
      };

      var updateEvt, updateSizes = {}, updateDebounce = 16;

      this.setSizes = function (sizes) {
        SIZE_LIST.forEach(function (name) {
          if (sizes[name] !== void 0) {
            updateSizes[name] = sizes[name];
          }
        });
      };
      this.setDebounce = function (deb) {
        updateDebounce = deb;
      };

      var start = function () {
        var
          style = getComputedStyle(document.body),
          target = window.visualViewport !== void 0
            ? window.visualViewport
            : window;

        // if css props available
        if (style.getPropertyValue('--q-size-sm')) {
          SIZE_LIST.forEach(function (name) {
            this$1.sizes[name] = parseInt(style.getPropertyValue(("--q-size-" + name)), 10);
          });
        }

        this$1.setSizes = function (sizes) {
          SIZE_LIST.forEach(function (name) {
            if (sizes[name]) {
              this$1.sizes[name] = sizes[name];
            }
          });
          update(true);
        };

        this$1.setDebounce = function (delay) {
          updateEvt !== void 0 && target.removeEventListener('resize', updateEvt, passive);
          updateEvt = delay > 0
            ? debounce(update, delay)
            : update;
          target.addEventListener('resize', updateEvt, passive);
        };

        this$1.setDebounce(updateDebounce);

        if (Object.keys(updateSizes).length > 0) {
          this$1.setSizes(updateSizes);
          updateSizes = void 0; // free up memory
        }
        else {
          update();
        }
      };

      if (fromSSR === true) {
        queues.takeover.push(start);
      }
      else {
        start();
      }

      Vue.util.defineReactive($q, 'screen', this);
    }
  };

  var Dark = {
    isActive: false,
    mode: false,

    install: function install ($q, queues, ref) {
      var this$1 = this;
      var dark = ref.dark;

      this.isActive = dark === true;

      if (isSSR === true) {
        queues.server.push(function (q, ctx) {
          q.dark = {
            isActive: false,
            mode: false,
            set: function (val) {
              ctx.ssr.Q_BODY_CLASSES = ctx.ssr.Q_BODY_CLASSES
                .replace(' body--light', '')
                .replace(' body--dark', '') + " body--" + (val === true ? 'dark' : 'light');

              q.dark.isActive = val === true;
              q.dark.mode = val;
            },
            toggle: function () {
              q.dark.set(q.dark.isActive === false);
            }
          };

          q.dark.set(dark);
        });

        this.set = noop;
        return
      }

      var initialVal = dark !== void 0
        ? dark
        : false;

      if (fromSSR === true) {
        var ssrSet = function (val) {
          this$1.__fromSSR = val;
        };

        var originalSet = this.set;

        this.set = ssrSet;
        ssrSet(initialVal);

        queues.takeover.push(function () {
          this$1.set = originalSet;
          this$1.set(this$1.__fromSSR);
        });
      }
      else {
        this.set(initialVal);
      }

      Vue.util.defineReactive(this, 'isActive', this.isActive);
      Vue.util.defineReactive($q, 'dark', this);
    },

    set: function set (val) {
      var this$1 = this;

      this.mode = val;

      if (val === 'auto') {
        if (this.__media === void 0) {
          this.__media = window.matchMedia('(prefers-color-scheme: dark)');
          this.__updateMedia = function () { this$1.set('auto'); };
          this.__media.addListener(this.__updateMedia);
        }

        val = this.__media.matches;
      }
      else if (this.__media !== void 0) {
        this.__media.removeListener(this.__updateMedia);
        this.__media = void 0;
      }

      this.isActive = val === true;

      document.body.classList.remove(("body--" + (val === true ? 'light' : 'dark')));
      document.body.classList.add(("body--" + (val === true ? 'dark' : 'light')));
    },

    toggle: function toggle () {
      Dark.set(Dark.isActive === false);
    },

    __media: void 0
  };

  var getTrue = function () { return true; };

  var History = {
    __history: [],
    add: noop,
    remove: noop,

    install: function install (cfg) {
      var this$1 = this;

      if (isSSR === true) {
        return
      }

      var ref = client.is;
      var cordova = ref.cordova;
      var capacitor = ref.capacitor;

      if (cordova !== true && capacitor !== true) {
        return
      }

      this.add = function (entry) {
        if (entry.condition === void 0) {
          entry.condition = getTrue;
        }
        this$1.__history.push(entry);
      };
      this.remove = function (entry) {
        var index = this$1.__history.indexOf(entry);
        if (index >= 0) {
          this$1.__history.splice(index, 1);
        }
      };

      var fn = function () {
        if (this$1.__history.length) {
          var entry = this$1.__history[this$1.__history.length - 1];

          if (entry.condition() === true) {
            this$1.__history.pop();
            entry.handler();
          }
        }
        else if (exit && window.location.hash === '#/') {
          navigator.app.exitApp();
        }
        else {
          window.history.back();
        }
      };

      var prop = cordova === true ? 'cordova' : 'capacitor';
      var exit = cfg[prop] === void 0 || cfg[prop].backButtonExit !== false;

      if (cordova === true) {
        document.addEventListener('deviceready', function () {
          document.addEventListener('backbutton', fn, false);
        });
      }
      else {
        window.Capacitor.Plugins.App.addListener('backButton', fn);
      }
    }
  };

  var langEn = {
    isoName: 'en-us',
    nativeName: 'English (US)',
    label: {
      clear: 'Clear',
      ok: 'OK',
      cancel: 'Cancel',
      close: 'Close',
      set: 'Set',
      select: 'Select',
      reset: 'Reset',
      remove: 'Remove',
      update: 'Update',
      create: 'Create',
      search: 'Search',
      filter: 'Filter',
      refresh: 'Refresh'
    },
    date: {
      days: 'Sunday_Monday_Tuesday_Wednesday_Thursday_Friday_Saturday'.split('_'),
      daysShort: 'Sun_Mon_Tue_Wed_Thu_Fri_Sat'.split('_'),
      months: 'January_February_March_April_May_June_July_August_September_October_November_December'.split('_'),
      monthsShort: 'Jan_Feb_Mar_Apr_May_Jun_Jul_Aug_Sep_Oct_Nov_Dec'.split('_'),
      firstDayOfWeek: 0, // 0-6, 0 - Sunday, 1 Monday, ...
      format24h: false
    },
    table: {
      noData: 'No data available',
      noResults: 'No matching records found',
      loading: 'Loading...',
      selectedRecords: function (rows) {
        return rows === 1
          ? '1 record selected.'
          : (rows === 0 ? 'No' : rows) + ' records selected.'
      },
      recordsPerPage: 'Records per page:',
      allRows: 'All',
      pagination: function (start, end, total) {
        return start + '-' + end + ' of ' + total
      },
      columns: 'Columns'
    },
    editor: {
      url: 'URL',
      bold: 'Bold',
      italic: 'Italic',
      strikethrough: 'Strikethrough',
      underline: 'Underline',
      unorderedList: 'Unordered List',
      orderedList: 'Ordered List',
      subscript: 'Subscript',
      superscript: 'Superscript',
      hyperlink: 'Hyperlink',
      toggleFullscreen: 'Toggle Fullscreen',
      quote: 'Quote',
      left: 'Left align',
      center: 'Center align',
      right: 'Right align',
      justify: 'Justify align',
      print: 'Print',
      outdent: 'Decrease indentation',
      indent: 'Increase indentation',
      removeFormat: 'Remove formatting',
      formatting: 'Formatting',
      fontSize: 'Font Size',
      align: 'Align',
      hr: 'Insert Horizontal Rule',
      undo: 'Undo',
      redo: 'Redo',
      heading1: 'Heading 1',
      heading2: 'Heading 2',
      heading3: 'Heading 3',
      heading4: 'Heading 4',
      heading5: 'Heading 5',
      heading6: 'Heading 6',
      paragraph: 'Paragraph',
      code: 'Code',
      size1: 'Very small',
      size2: 'A bit small',
      size3: 'Normal',
      size4: 'Medium-large',
      size5: 'Big',
      size6: 'Very big',
      size7: 'Maximum',
      defaultFont: 'Default Font',
      viewSource: 'View Source'
    },
    tree: {
      noNodes: 'No nodes available',
      noResults: 'No matching nodes found'
    }
  };

  var lang = {
    install: function install ($q, queues, lang) {
      var this$1 = this;

      if (isSSR === true) {
        queues.server.push(function (q, ctx) {
          var
            opt = {
              lang: q.lang.isoName,
              dir: q.lang.rtl === true ? 'rtl' : 'ltr'
            },
            fn = ctx.ssr.setHtmlAttrs;

          if (typeof fn === 'function') {
            fn(opt);
          }
          else {
            ctx.ssr.Q_HTML_ATTRS = Object.keys(opt)
              .map(function (key) { return (key + "=" + (opt[key])); })
              .join(' ');
          }
        });
      }

      this.set = function (lang) {
        if ( lang === void 0 ) lang = langEn;

        lang.set = this$1.set;
        lang.getLocale = this$1.getLocale;
        lang.rtl = lang.rtl === true || false;

        if (isSSR === false) {
          var el = document.documentElement;
          el.setAttribute('dir', lang.rtl ? 'rtl' : 'ltr');
          el.setAttribute('lang', lang.isoName);
        }

        if (isSSR === true || $q.lang !== void 0) {
          $q.lang = lang;
        }
        else {
          Vue.util.defineReactive($q, 'lang', lang);
        }

        this$1.isoName = lang.isoName;
        this$1.nativeName = lang.nativeName;
        this$1.props = lang;
      };

      this.set(lang);
    },

    getLocale: function getLocale () {
      if (isSSR === true) { return }

      var val =
        navigator.language ||
        navigator.languages[0] ||
        navigator.browserLanguage ||
        navigator.userLanguage ||
        navigator.systemLanguage;

      if (val) {
        return val.toLowerCase()
      }
    }
  };

  function rgbToHex (ref) {
    var r = ref.r;
    var g = ref.g;
    var b = ref.b;
    var a = ref.a;

    var alpha = a !== void 0;

    r = Math.round(r);
    g = Math.round(g);
    b = Math.round(b);

    if (
      r > 255 ||
      g > 255 ||
      b > 255 ||
      (alpha && a > 100)
    ) {
      throw new TypeError('Expected 3 numbers below 256 (and optionally one below 100)')
    }

    a = alpha
      ? (Math.round(255 * a / 100) | 1 << 8).toString(16).slice(1)
      : '';

    return '#' + ((b | g << 8 | r << 16) | 1 << 24).toString(16).slice(1) + a
  }

  function rgbToString (ref) {
    var r = ref.r;
    var g = ref.g;
    var b = ref.b;
    var a = ref.a;

    return ("rgb" + (a !== void 0 ? 'a' : '') + "(" + r + "," + g + "," + b + (a !== void 0 ? ',' + (a / 100) : '') + ")")
  }

  function stringToRgb (str) {
    if (typeof str !== 'string') {
      throw new TypeError('Expected a string')
    }

    str = str.replace(/ /g, '');

    if (str.startsWith('#')) {
      return hexToRgb(str)
    }

    var model = str.substring(str.indexOf('(') + 1, str.length - 1).split(',');

    return {
      r: parseInt(model[0], 10),
      g: parseInt(model[1], 10),
      b: parseInt(model[2], 10),
      a: model[3] !== void 0 ? parseFloat(model[3]) * 100 : void 0
    }
  }

  function hexToRgb (hex) {
    if (typeof hex !== 'string') {
      throw new TypeError('Expected a string')
    }

    hex = hex.replace(/^#/, '');

    if (hex.length === 3) {
      hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
    }
    else if (hex.length === 4) {
      hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3];
    }

    var num = parseInt(hex, 16);

    return hex.length > 6
      ? { r: num >> 24 & 255, g: num >> 16 & 255, b: num >> 8 & 255, a: Math.round((num & 255) / 2.55) }
      : { r: num >> 16, g: num >> 8 & 255, b: num & 255 }
  }

  function hsvToRgb (ref) {
    var h = ref.h;
    var s = ref.s;
    var v = ref.v;
    var a = ref.a;

    var r, g, b, i, f, p, q, t;
    s = s / 100;
    v = v / 100;

    h = h / 360;
    i = Math.floor(h * 6);
    f = h * 6 - i;
    p = v * (1 - s);
    q = v * (1 - f * s);
    t = v * (1 - (1 - f) * s);

    switch (i % 6) {
      case 0:
        r = v;
        g = t;
        b = p;
        break
      case 1:
        r = q;
        g = v;
        b = p;
        break
      case 2:
        r = p;
        g = v;
        b = t;
        break
      case 3:
        r = p;
        g = q;
        b = v;
        break
      case 4:
        r = t;
        g = p;
        b = v;
        break
      case 5:
        r = v;
        g = p;
        b = q;
        break
    }

    return {
      r: Math.round(r * 255),
      g: Math.round(g * 255),
      b: Math.round(b * 255),
      a: a
    }
  }

  function rgbToHsv (ref) {
    var r = ref.r;
    var g = ref.g;
    var b = ref.b;
    var a = ref.a;

    var
      max = Math.max(r, g, b), min = Math.min(r, g, b),
      d = max - min,
      h,
      s = (max === 0 ? 0 : d / max),
      v = max / 255;

    switch (max) {
      case min:
        h = 0;
        break
      case r:
        h = (g - b) + d * (g < b ? 6 : 0);
        h /= 6 * d;
        break
      case g:
        h = (b - r) + d * 2;
        h /= 6 * d;
        break
      case b:
        h = (r - g) + d * 4;
        h /= 6 * d;
        break
    }

    return {
      h: Math.round(h * 360),
      s: Math.round(s * 100),
      v: Math.round(v * 100),
      a: a
    }
  }

  var reRGBA = /^rgb(a)?\((\d{1,3}),(\d{1,3}),(\d{1,3}),?([01]?\.?\d*?)?\)$/;

  function textToRgb (str) {
    if (typeof str !== 'string') {
      throw new TypeError('Expected a string')
    }

    var color = str.replace(/ /g, '');

    var m = reRGBA.exec(color);

    if (m === null) {
      return hexToRgb(color)
    }

    var rgb = {
      r: Math.min(255, parseInt(m[2], 10)),
      g: Math.min(255, parseInt(m[3], 10)),
      b: Math.min(255, parseInt(m[4], 10))
    };

    if (m[1]) {
      var alpha = parseFloat(m[5]);
      rgb.a = Math.min(1, isNaN(alpha) === true ? 1 : alpha) * 100;
    }

    return rgb
  }

  /* works as darken if percent < 0 */
  function lighten (color, percent) {
    if (typeof color !== 'string') {
      throw new TypeError('Expected a string as color')
    }
    if (typeof percent !== 'number') {
      throw new TypeError('Expected a numeric percent')
    }

    var rgb = textToRgb(color),
      t = percent < 0 ? 0 : 255,
      p = Math.abs(percent) / 100,
      R = rgb.r,
      G = rgb.g,
      B = rgb.b;

    return '#' + (
      0x1000000 + (Math.round((t - R) * p) + R) * 0x10000 +
      (Math.round((t - G) * p) + G) * 0x100 +
      (Math.round((t - B) * p) + B)
    ).toString(16).slice(1)
  }

  function luminosity (color) {
    if (typeof color !== 'string' && (!color || color.r === void 0)) {
      throw new TypeError('Expected a string or a {r, g, b} object as color')
    }

    var
      rgb = typeof color === 'string' ? textToRgb(color) : color,
      r = rgb.r / 255,
      g = rgb.g / 255,
      b = rgb.b / 255,
      R = r <= 0.03928 ? r / 12.92 : Math.pow((r + 0.055) / 1.055, 2.4),
      G = g <= 0.03928 ? g / 12.92 : Math.pow((g + 0.055) / 1.055, 2.4),
      B = b <= 0.03928 ? b / 12.92 : Math.pow((b + 0.055) / 1.055, 2.4);
    return 0.2126 * R + 0.7152 * G + 0.0722 * B
  }

  function brightness (color) {
    if (typeof color !== 'string' && (!color || color.r === void 0)) {
      throw new TypeError('Expected a string or a {r, g, b} object as color')
    }

    var rgb = typeof color === 'string'
      ? textToRgb(color)
      : color;

    return (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000
  }

  function blend (fgColor, bgColor) {
    if (typeof fgColor !== 'string' && (!fgColor || fgColor.r === void 0)) {
      throw new TypeError('Expected a string or a {r, g, b[, a]} object as fgColor')
    }

    if (typeof bgColor !== 'string' && (!bgColor || bgColor.r === void 0)) {
      throw new TypeError('Expected a string or a {r, g, b[, a]} object as bgColor')
    }

    var
      rgb1 = typeof fgColor === 'string' ? textToRgb(fgColor) : fgColor,
      r1 = rgb1.r / 255,
      g1 = rgb1.g / 255,
      b1 = rgb1.b / 255,
      a1 = rgb1.a !== void 0 ? rgb1.a / 100 : 1,
      rgb2 = typeof bgColor === 'string' ? textToRgb(bgColor) : bgColor,
      r2 = rgb2.r / 255,
      g2 = rgb2.g / 255,
      b2 = rgb2.b / 255,
      a2 = rgb2.a !== void 0 ? rgb2.a / 100 : 1,
      a = a1 + a2 * (1 - a1),
      r = Math.round(((r1 * a1 + r2 * a2 * (1 - a1)) / a) * 255),
      g = Math.round(((g1 * a1 + g2 * a2 * (1 - a1)) / a) * 255),
      b = Math.round(((b1 * a1 + b2 * a2 * (1 - a1)) / a) * 255);

    var ret = { r: r, g: g, b: b, a: Math.round(a * 100) };
    return typeof fgColor === 'string'
      ? rgbToHex(ret)
      : ret
  }

  function changeAlpha (color, offset) {
    if (typeof color !== 'string') {
      throw new TypeError('Expected a string as color')
    }

    if (offset === void 0 || offset < -1 || offset > 1) {
      throw new TypeError('Expected offset to be between -1 and 1')
    }

    var ref = textToRgb(color);
    var r = ref.r;
    var g = ref.g;
    var b = ref.b;
    var a = ref.a;
    var alpha = a !== void 0 ? a / 100 : 0;

    return rgbToHex({
      r: r, g: g, b: b, a: Math.round(Math.min(1, Math.max(0, alpha + offset)) * 100)
    })
  }

  function setBrand (color, value, element) {
    if ( element === void 0 ) element = document.body;

    if (typeof color !== 'string') {
      throw new TypeError('Expected a string as color')
    }
    if (typeof value !== 'string') {
      throw new TypeError('Expected a string as value')
    }
    if (!(element instanceof Element)) {
      throw new TypeError('Expected a DOM element')
    }

    element.style.setProperty(("--q-color-" + color), value);
  }

  function getBrand (color, element) {
    if ( element === void 0 ) element = document.body;

    if (typeof color !== 'string') {
      throw new TypeError('Expected a string as color')
    }
    if (!(element instanceof Element)) {
      throw new TypeError('Expected a DOM element')
    }

    return getComputedStyle(element).getPropertyValue(("--q-color-" + color)).trim() || null
  }

  var colors = {
    rgbToHex: rgbToHex,
    hexToRgb: hexToRgb,
    hsvToRgb: hsvToRgb,
    rgbToHsv: rgbToHsv,
    textToRgb: textToRgb,
    lighten: lighten,
    luminosity: luminosity,
    brightness: brightness,
    blend: blend,
    changeAlpha: changeAlpha,
    setBrand: setBrand,
    getBrand: getBrand
  };

  var lastKeyCompositionStatus = false;

  function onKeyDownComposition (evt) {
    lastKeyCompositionStatus = evt.isComposing === true;
  }

  function shouldIgnoreKey (evt) {
    return lastKeyCompositionStatus === true ||
      evt !== Object(evt) ||
      evt.isComposing === true ||
      evt.qKeyEvent === true
  }

  function isKeyCode (evt, keyCodes) {
    return (
      lastKeyCompositionStatus === true ||
      evt !== Object(evt) ||
      evt.isComposing === true ||
      evt.qKeyEvent === true
    )
      ? false
      : [].concat(keyCodes).includes(evt.keyCode)
  }

  function getMobilePlatform (is) {
    if (is.ios === true) { return 'ios' }
    if (is.android === true) { return 'android' }
  }

  function getBodyClasses (ref, cfg) {
    var is = ref.is;
    var has = ref.has;
    var within = ref.within;

    var cls = [
      is.desktop === true ? 'desktop' : 'mobile',
      ((has.touch === false ? 'no-' : '') + "touch")
    ];

    if (is.mobile === true) {
      var mobile = getMobilePlatform(is);
      mobile !== void 0 && cls.push('platform-' + mobile);
    }

    if (is.nativeMobile === true) {
      var type = is.nativeMobileWrapper;

      cls.push(type);
      cls.push('native-mobile');

      if (
        is.ios === true &&
        (cfg[type] === void 0 || cfg[type].iosStatusBarPadding !== false)
      ) {
        cls.push('q-ios-padding');
      }
    }
    else if (is.electron === true) {
      cls.push('electron');
    }
    else if (is.bex === true) {
      cls.push('bex');
    }

    within.iframe === true && cls.push('within-iframe');

    return cls
  }

  // SSR takeover corrections
  function clientUpdate () {
    var classes = document.body.className;
    var newCls = classes;

    if (iosCorrection !== void 0) {
      newCls = newCls.replace('desktop', 'platform-ios mobile');
    }

    if (client.has.touch === true) {
      newCls = newCls.replace('no-touch', 'touch');
    }

    if (client.within.iframe === true) {
      newCls += ' within-iframe';
    }

    if (classes !== newCls) {
      document.body.className = newCls;
    }
  }

  function setColors (brand) {
    for (var color in brand) {
      setBrand(color, brand[color]);
    }
  }

  var Body = {
    install: function install (queues, cfg) {
      if (isSSR === true) {
        queues.server.push(function (q, ctx) {
          var
            cls = getBodyClasses(q.platform, cfg),
            fn = ctx.ssr.setBodyClasses;

          if (cfg.screen !== void 0 && cfg.screen.bodyClass === true) {
            cls.push('screen--xs');
          }

          if (typeof fn === 'function') {
            fn(cls);
          }
          else {
            ctx.ssr.Q_BODY_CLASSES = cls.join(' ');
          }
        });

        return
      }

      if (fromSSR === true) {
        clientUpdate();
      }
      else {
        var cls = getBodyClasses(client, cfg);

        if (client.is.ie === true && client.is.versionNumber === 11) {
          cls.forEach(function (c) { return document.body.classList.add(c); });
        }
        else {
          document.body.classList.add.apply(document.body.classList, cls);
        }
      }

      cfg.brand !== void 0 && setColors(cfg.brand);

      if (client.is.ios === true) {
        // needed for iOS button active state
        document.body.addEventListener('touchstart', noop);
      }

      window.addEventListener('keydown', onKeyDownComposition, true);
    }
  };

  var materialIcons = {
    name: 'material-icons',
    type: {
      positive: 'check_circle',
      negative: 'warning',
      info: 'info',
      warning: 'priority_high'
    },
    arrow: {
      up: 'arrow_upward',
      right: 'arrow_forward',
      down: 'arrow_downward',
      left: 'arrow_back',
      dropdown: 'arrow_drop_down'
    },
    chevron: {
      left: 'chevron_left',
      right: 'chevron_right'
    },
    colorPicker: {
      spectrum: 'gradient',
      tune: 'tune',
      palette: 'style'
    },
    pullToRefresh: {
      icon: 'refresh'
    },
    carousel: {
      left: 'chevron_left',
      right: 'chevron_right',
      up: 'keyboard_arrow_up',
      down: 'keyboard_arrow_down',
      navigationIcon: 'lens'
    },
    chip: {
      remove: 'cancel',
      selected: 'check'
    },
    datetime: {
      arrowLeft: 'chevron_left',
      arrowRight: 'chevron_right',
      now: 'access_time',
      today: 'today'
    },
    editor: {
      bold: 'format_bold',
      italic: 'format_italic',
      strikethrough: 'strikethrough_s',
      underline: 'format_underlined',
      unorderedList: 'format_list_bulleted',
      orderedList: 'format_list_numbered',
      subscript: 'vertical_align_bottom',
      superscript: 'vertical_align_top',
      hyperlink: 'link',
      toggleFullscreen: 'fullscreen',
      quote: 'format_quote',
      left: 'format_align_left',
      center: 'format_align_center',
      right: 'format_align_right',
      justify: 'format_align_justify',
      print: 'print',
      outdent: 'format_indent_decrease',
      indent: 'format_indent_increase',
      removeFormat: 'format_clear',
      formatting: 'text_format',
      fontSize: 'format_size',
      align: 'format_align_left',
      hr: 'remove',
      undo: 'undo',
      redo: 'redo',
      heading: 'format_size',
      code: 'code',
      size: 'format_size',
      font: 'font_download',
      viewSource: 'code'
    },
    expansionItem: {
      icon: 'keyboard_arrow_down',
      denseIcon: 'arrow_drop_down'
    },
    fab: {
      icon: 'add',
      activeIcon: 'close'
    },
    field: {
      clear: 'cancel',
      error: 'error'
    },
    pagination: {
      first: 'first_page',
      prev: 'keyboard_arrow_left',
      next: 'keyboard_arrow_right',
      last: 'last_page'
    },
    rating: {
      icon: 'grade'
    },
    stepper: {
      done: 'check',
      active: 'edit',
      error: 'warning'
    },
    tabs: {
      left: 'chevron_left',
      right: 'chevron_right',
      up: 'keyboard_arrow_up',
      down: 'keyboard_arrow_down'
    },
    table: {
      arrowUp: 'arrow_upward',
      warning: 'warning',
      prevPage: 'chevron_left',
      nextPage: 'chevron_right'
    },
    tree: {
      icon: 'play_arrow'
    },
    uploader: {
      done: 'done',
      clear: 'clear',
      add: 'add_box',
      upload: 'cloud_upload',
      removeQueue: 'clear_all',
      removeUploaded: 'done_all'
    }
  };

  var iconSet = {
    install: function install ($q, iconSet) {
      var this$1 = this;

      this.set = function (iconDef) {
        if ( iconDef === void 0 ) iconDef = materialIcons;

        iconDef.set = this$1.set;

        if (isSSR === true || $q.iconSet !== void 0) {
          $q.iconSet = iconDef;
        }
        else {
          Vue.util.defineReactive($q, 'iconSet', iconDef);
        }

        this$1.name = iconDef.name;
        this$1.def = iconDef;
      };

      this.set(iconSet);

      if (isSSR !== true) {
        Vue.util.defineReactive($q, 'iconMapFn', void 0);
      }
    }
  };

  var autoInstalled = [
    Platform, Screen, Dark
  ];

  var queues = {
    server: [], // on SSR update
    takeover: [] // on client takeover
  };

  var $q = {
    version: version
  };

  function install (Vue, opts) {
    if ( opts === void 0 ) opts = {};

    if (this.__qInstalled === true) { return }
    this.__qInstalled = true;

    var cfg = opts.config || {};

    // required plugins
    Platform.install($q, queues);
    Body.install(queues, cfg);
    Dark.install($q, queues, cfg);
    Screen.install($q, queues, cfg);
    History.install(cfg);
    lang.install($q, queues, opts.lang);
    iconSet.install($q, opts.iconSet);

    if (isSSR === true) {
      Vue.mixin({
        beforeCreate: function beforeCreate () {
          this.$q = this.$root.$options.$q;
        }
      });
    }
    else {
      Vue.prototype.$q = $q;
    }

    opts.components && Object.keys(opts.components).forEach(function (key) {
      var c = opts.components[key];
      if (typeof c === 'function') {
        Vue.component(c.options.name, c);
      }
    });

    opts.directives && Object.keys(opts.directives).forEach(function (key) {
      var d = opts.directives[key];
      if (d.name !== undefined && d.unbind !== void 0) {
        Vue.directive(d.name, d);
      }
    });

    if (opts.plugins) {
      var param = { $q: $q, queues: queues, cfg: cfg };
      Object.keys(opts.plugins).forEach(function (key) {
        var p = opts.plugins[key];
        if (typeof p.install === 'function' && autoInstalled.includes(p) === false) {
          p.install(param);
        }
      });
    }
  }

  var units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

  function humanStorageSize (bytes) {
    var u = 0;

    while (parseInt(bytes, 10) >= 1024 && u < units.length - 1) {
      bytes /= 1024;
      ++u;
    }

    return ((bytes.toFixed(1)) + " " + (units[u]))
  }

  function capitalize (str) {
    return str.charAt(0).toUpperCase() + str.slice(1)
  }

  function between (v, min, max) {
    return max <= min
      ? min
      : Math.min(max, Math.max(min, v))
  }

  function normalizeToInterval (v, min, max) {
    if (max <= min) {
      return min
    }

    var size = (max - min + 1);

    var index = min + (v - min) % size;
    if (index < min) {
      index = size + index;
    }

    return index === 0 ? 0 : index // fix for (-a % a) => -0
  }

  function pad (v, length, char) {
    if ( length === void 0 ) length = 2;
    if ( char === void 0 ) char = '0';

    if (v === void 0 || v === null) {
      return v
    }

    var val = '' + v;
    return val.length >= length
      ? val
      : new Array(length - val.length + 1).join(char) + val
  }

  var format = {
    humanStorageSize: humanStorageSize,
    capitalize: capitalize,
    between: between,
    normalizeToInterval: normalizeToInterval,
    pad: pad
  };

  var
    xhr = isSSR ? null : XMLHttpRequest,
    send = isSSR ? null : xhr.prototype.send,
    stackStart = [],
    stackStop = [];

  var highjackCount = 0;

  function translate (ref) {
    var p = ref.p;
    var pos = ref.pos;
    var active = ref.active;
    var horiz = ref.horiz;
    var reverse = ref.reverse;
    var dir = ref.dir;

    var x = 1, y = 1;

    if (horiz) {
      if (reverse) { x = -1; }
      if (pos === 'bottom') { y = -1; }
      return { transform: ("translate3d(" + (x * (p - 100)) + "%," + (active ? 0 : y * -200) + "%,0)") }
    }

    if (reverse) { y = -1; }
    if (pos === 'right') { x = -1; }
    return { transform: ("translate3d(" + (active ? 0 : dir * x * -200) + "%," + (y * (p - 100)) + "%,0)") }
  }

  function inc (p, amount) {
    if (typeof amount !== 'number') {
      if (p < 25) {
        amount = Math.random() * 3 + 3;
      }
      else if (p < 65) {
        amount = Math.random() * 3;
      }
      else if (p < 85) {
        amount = Math.random() * 2;
      }
      else if (p < 99) {
        amount = 0.6;
      }
      else {
        amount = 0;
      }
    }
    return between(p + amount, 0, 100)
  }

  function highjackAjax (start, stop) {
    stackStart.push(start);
    stackStop.push(stop);

    highjackCount++;

    if (highjackCount > 1) { return }

    function endHandler () {
      stackStop.forEach(function (fn) { fn(); });
    }

    xhr.prototype.send = function (/* ...args */) {
      stackStart.forEach(function (fn) { fn(); });
      this.addEventListener('loadend', endHandler, false);
      send.apply(this, arguments);
    };
  }

  function restoreAjax (start, stop) {
    stackStart.splice(stackStart.indexOf(start), 1);
    stackStop.splice(stackStop.indexOf(stop), 1);

    highjackCount = Math.max(0, highjackCount - 1);
    if (!highjackCount) {
      xhr.prototype.send = send;
    }
  }

  var QAjaxBar = Vue.extend({
    name: 'QAjaxBar',

    props: {
      position: {
        type: String,
        default: 'top',
        validator: function (val) { return ['top', 'right', 'bottom', 'left'].includes(val); }
      },
      size: {
        type: String,
        default: '2px'
      },
      color: {
        type: String,
        default: 'red'
      },
      skipHijack: Boolean,
      reverse: Boolean
    },

    data: function data () {
      return {
        calls: 0,
        progress: 0,
        onScreen: false,
        animate: true
      }
    },

    computed: {
      classes: function classes () {
        return "q-loading-bar q-loading-bar--" + (this.position) + " bg-" + (this.color) +
          (this.animate === true ? '' : ' no-transition')
      },

      style: function style () {
        var active = this.onScreen;

        var o = translate({
          p: this.progress,
          pos: this.position,
          active: active,
          horiz: this.horizontal,
          reverse: this.$q.lang.rtl === true && ['top', 'bottom'].includes(this.position)
            ? !this.reverse
            : this.reverse,
          dir: this.$q.lang.rtl === true ? -1 : 1
        });

        o[this.sizeProp] = this.size;
        o.opacity = active ? 1 : 0;

        return o
      },

      horizontal: function horizontal () {
        return this.position === 'top' || this.position === 'bottom'
      },

      sizeProp: function sizeProp () {
        return this.horizontal ? 'height' : 'width'
      },

      attrs: function attrs () {
        return this.onScreen === true
          ? {
            role: 'progressbar',
            'aria-valuemin': 0,
            'aria-valuemax': 100,
            'aria-valuenow': this.progress
          }
          : {
            'aria-hidden': 'true'
          }
      }
    },

    methods: {
      start: function start (speed) {
        var this$1 = this;
        if ( speed === void 0 ) speed = 300;

        var oldSpeed = this.speed;
        this.speed = Math.max(0, speed) || 0;

        this.calls++;

        if (this.calls > 1) {
          if (oldSpeed === 0 && speed > 0) {
            this.__work();
          }
          else if (oldSpeed > 0 && speed <= 0) {
            clearTimeout(this.timer);
          }
          return
        }

        clearTimeout(this.timer);
        this.$emit('start');

        this.progress = 0;

        if (this.onScreen === true) { return }

        this.onScreen = true;
        this.animate = false;
        this.timer = setTimeout(function () {
          this$1.animate = true;
          speed > 0 && this$1.__work();
        }, 100);
      },

      increment: function increment (amount) {
        this.calls > 0 && (this.progress = inc(this.progress, amount));
      },

      stop: function stop () {
        var this$1 = this;

        this.calls = Math.max(0, this.calls - 1);
        if (this.calls > 0) { return }

        clearTimeout(this.timer);
        this.$emit('stop');

        var end = function () {
          this$1.animate = true;
          this$1.progress = 100;
          this$1.timer = setTimeout(function () {
            this$1.onScreen = false;
          }, 1000);
        };

        if (this.progress === 0) {
          this.timer = setTimeout(end, 1);
        }
        else {
          end();
        }
      },

      __work: function __work () {
        var this$1 = this;

        if (this.progress < 100) {
          this.timer = setTimeout(function () {
            this$1.increment();
            this$1.__work();
          }, this.speed);
        }
      }
    },

    mounted: function mounted () {
      if (this.skipHijack !== true) {
        this.hijacked = true;
        highjackAjax(this.start, this.stop);
      }
    },

    beforeDestroy: function beforeDestroy () {
      clearTimeout(this.timer);
      this.hijacked && restoreAjax(this.start, this.stop);
    },

    render: function render (h) {
      return h('div', {
        class: this.classes,
        style: this.style,
        attrs: this.attrs
      })
    }
  });

  var sizes = {
    xs: 18,
    sm: 24,
    md: 32,
    lg: 38,
    xl: 46
  };

  function getSizeMixin (sizes) {
    return {
      props: {
        size: String
      },

      computed: {
        sizeStyle: function sizeStyle () {
          if (this.size !== void 0) {
            return { fontSize: this.size in sizes ? ((sizes[this.size]) + "px") : this.size }
          }
        }
      }
    }
  }

  var SizeMixin = getSizeMixin(sizes);

  var TagMixin = {
    props: {
      tag: {
        type: String,
        default: 'div'
      }
    }
  };

  function slot (vm, slotName, otherwise) {
    return vm.$scopedSlots[slotName] !== void 0
      ? vm.$scopedSlots[slotName]()
      : otherwise
  }

  function uniqueSlot (vm, slotName, otherwise) {
    return vm.$scopedSlots[slotName] !== void 0
      ? vm.$scopedSlots[slotName]().slice()
      : otherwise
  }

  /**
   * Source definitely exists,
   * so it's merged with the possible slot
   */
  function mergeSlot (source, vm, slotName) {
    return vm.$scopedSlots[slotName] !== void 0
      ? source.concat(vm.$scopedSlots[slotName]())
      : source
  }

  /**
   * Merge with possible slot,
   * even if source might not exist
   */
  function mergeSlotSafely (source, vm, slotName) {
    if (vm.$scopedSlots[slotName] === void 0) {
      return source
    }

    var slot = vm.$scopedSlots[slotName]();
    return source !== void 0
      ? source.concat(slot)
      : slot
  }

  var QIcon = Vue.extend({
    name: 'QIcon',

    mixins: [ SizeMixin, TagMixin ],

    props: {
      tag: {
        default: 'i'
      },

      name: String,
      color: String,
      left: Boolean,
      right: Boolean
    },

    computed: {
      classes: function classes () {
        // "notranslate" class is for Google Translate
        // to avoid tampering with Material Icons ligature font
        return 'q-icon notranslate' +
          (this.left === true ? ' on-left' : '') +
          (this.right === true ? ' on-right' : '') +
          (this.color !== void 0 ? (" text-" + (this.color)) : '')
      },

      type: function type () {
        var cls;
        var icon = this.name;

        if (!icon) {
          return {
            none: true,
            cls: this.classes
          }
        }

        if (this.$q.iconMapFn !== void 0) {
          var res = this.$q.iconMapFn(icon);
          if (res !== void 0) {
            if (res.icon !== void 0) {
              icon = res.icon;
            }
            else {
              return {
                cls: res.cls + ' ' + this.classes,
                content: res.content !== void 0
                  ? res.content
                  : ' '
              }
            }
          }
        }

        if (icon.startsWith('M') === true) {
          var cfg = icon.split('|');
          return {
            svg: true,
            cls: this.classes,
            path: cfg[0],
            viewBox: cfg[1] !== void 0 ? cfg[1] : '0 0 24 24'
          }
        }

        if (icon.startsWith('img:') === true) {
          return {
            img: true,
            cls: this.classes,
            src: icon.substring(4)
          }
        }

        var content = ' ';

        if (/^[l|f]a[s|r|l|b|d]{0,1} /.test(icon) || icon.startsWith('icon-') === true) {
          cls = icon;
        }
        else if (icon.startsWith('bt-') === true) {
          cls = "bt " + icon;
        }
        else if (icon.startsWith('eva-') === true) {
          cls = "eva " + icon;
        }
        else if (/^ion-(md|ios|logo)/.test(icon) === true) {
          cls = "ionicons " + icon;
        }
        else if (icon.startsWith('ion-') === true) {
          cls = "ionicons ion-" + (this.$q.platform.is.ios === true ? 'ios' : 'md') + (icon.substr(3));
        }
        else if (icon.startsWith('mdi-') === true) {
          cls = "mdi " + icon;
        }
        else if (icon.startsWith('iconfont ') === true) {
          cls = "" + icon;
        }
        else if (icon.startsWith('ti-') === true) {
          cls = "themify-icon " + icon;
        }
        else {
          cls = 'material-icons';

          if (icon.startsWith('o_') === true) {
            icon = icon.substring(2);
            cls += '-outlined';
          }
          else if (icon.startsWith('r_') === true) {
            icon = icon.substring(2);
            cls += '-round';
          }
          else if (icon.startsWith('s_') === true) {
            icon = icon.substring(2);
            cls += '-sharp';
          }

          content = icon;
        }

        return {
          cls: cls + ' ' + this.classes,
          content: content
        }
      }
    },

    render: function render (h) {
      var data = {
        class: this.type.cls,
        style: this.sizeStyle,
        on: this.$listeners,
        attrs: {
          'aria-hidden': 'true',
          role: 'presentation'
        }
      };

      if (this.type.none === true) {
        return h(this.tag, data, slot(this, 'default'))
      }

      if (this.type.img === true) {
        data.attrs.src = this.type.src;
        return h('img', data)
      }

      if (this.type.svg === true) {
        data.attrs.focusable = 'false'; /* needed for IE11 */
        data.attrs.viewBox = this.type.viewBox;

        return h('svg', data, mergeSlot([
          h('path', {
            attrs: { d: this.type.path }
          })
        ], this, 'default'))
      }

      return h(this.tag, data, mergeSlot([
        this.type.content
      ], this, 'default'))
    }
  });

  var QAvatar = Vue.extend({
    name: 'QAvatar',

    mixins: [ SizeMixin ],

    props: {
      fontSize: String,

      color: String,
      textColor: String,

      icon: String,
      square: Boolean,
      rounded: Boolean
    },

    computed: {
      contentClass: function contentClass () {
        var obj;

        return ( obj = {}, obj[("bg-" + (this.color))] = this.color, obj[("text-" + (this.textColor) + " q-chip--colored")] = this.textColor, obj['q-avatar__content--square'] = this.square, obj['rounded-borders'] = this.rounded, obj )
      },

      contentStyle: function contentStyle () {
        if (this.fontSize) {
          return { fontSize: this.fontSize }
        }
      }
    },

    render: function render (h) {
      var icon = this.icon !== void 0
        ? [ h(QIcon, { props: { name: this.icon } }) ]
        : void 0;

      return h('div', {
        staticClass: 'q-avatar',
        style: this.sizeStyle,
        on: this.$listeners
      }, [
        h('div', {
          staticClass: 'q-avatar__content row flex-center overflow-hidden',
          class: this.contentClass,
          style: this.contentStyle
        }, mergeSlotSafely(icon, this, 'default'))
      ])
    }
  });

  var QBadge = Vue.extend({
    name: 'QBadge',

    props: {
      color: String,
      textColor: String,

      floating: Boolean,
      transparent: Boolean,
      multiLine: Boolean,
      outline: Boolean,

      label: [Number, String],

      align: {
        type: String,
        validator: function (v) { return ['top', 'middle', 'bottom'].includes(v); }
      }
    },

    computed: {
      style: function style () {
        if (this.align !== void 0) {
          return { verticalAlign: this.align }
        }
      },

      classes: function classes () {
        var text = this.outline === true
          ? this.color || this.textColor
          : this.textColor;

        return 'q-badge flex inline items-center no-wrap' +
          " q-badge--" + (this.multiLine === true ? 'multi' : 'single') + "-line" +
          (this.outline === true
            ? ' q-badge--outline'
            : (this.color !== void 0 ? (" bg-" + (this.color)) : '')
          ) +
          (text !== void 0 ? (" text-" + text) : '') +
          (this.floating === true ? ' q-badge--floating' : '') +
          (this.transparent === true ? ' q-badge--transparent' : '')
      },

      attrs: function attrs () {
        return {
          role: 'alert',
          'aria-label': this.label
        }
      }
    },

    render: function render (h) {
      return h('div', {
        style: this.style,
        class: this.classes,
        attrs: this.attrs,
        on: this.$listeners
      }, this.label !== void 0 ? [ this.label ] : slot(this, 'default'))
    }
  });

  var DarkMixin = {
    props: {
      dark: {
        type: Boolean,
        default: null
      }
    },

    computed: {
      isDark: function isDark () {
        return this.dark === null
          ? this.$q.dark.isActive
          : this.dark
      }
    }
  };

  var attrs = { role: 'alert' };

  var QBanner = Vue.extend({
    name: 'QBanner',

    mixins: [ DarkMixin ],

    props: {
      inlineActions: Boolean,
      dense: Boolean,
      rounded: Boolean
    },

    render: function render (h) {
      var actions = slot(this, 'action');
      var child = [
        h('div', {
          staticClass: 'q-banner__avatar col-auto row items-center'
        }, slot(this, 'avatar')),

        h('div', {
          staticClass: 'q-banner__content col text-body2'
        }, slot(this, 'default'))
      ];

      actions !== void 0 && child.push(
        h('div', {
          staticClass: 'q-banner__actions row items-center justify-end',
          class: ("col-" + (this.inlineActions === true ? 'auto' : 'all'))
        }, actions)
      );

      return h('div', {
        staticClass: 'q-banner row items-center',
        class: {
          'q-banner--top-padding': actions !== void 0 && !this.inlineActions,
          'q-banner--dense': this.dense,
          'q-banner--dark q-dark': this.isDark,
          'rounded-borders': this.rounded
        },
        attrs: attrs,
        on: this.$listeners
      }, child)
    }
  });

  var attrs$1 = { role: 'toolbar' };

  var QBar = Vue.extend({
    name: 'QBar',

    mixins: [ DarkMixin ],

    props: {
      dense: Boolean
    },

    computed: {
      classes: function classes () {
        return "q-bar--" + (this.dense === true ? 'dense' : 'standard') + " " +
          "q-bar--" + (this.isDark === true ? 'dark' : 'light')
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-bar row no-wrap items-center',
        class: this.classes,
        attrs: attrs$1,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var
    alignMap = {
      left: 'start',
      center: 'center',
      right: 'end',
      between: 'between',
      around: 'around',
      evenly: 'evenly',
      stretch: 'stretch'
    },
    alignValues = Object.keys(alignMap);

  var AlignMixin = {
    props: {
      align: {
        type: String,
        validator: function (v) { return alignValues.includes(v); }
      }
    },

    computed: {
      alignClass: function alignClass () {
        var align = this.align === void 0
          ? (this.vertical === true ? 'stretch' : 'left')
          : this.align;

        return ((this.vertical === true ? 'items' : 'justify') + "-" + (alignMap[align]))
      }
    }
  };

  var QBreadcrumbs = Vue.extend({
    name: 'QBreadcrumbs',

    mixins: [ AlignMixin ],

    props: {
      separator: {
        type: String,
        default: '/'
      },
      separatorColor: String,

      activeColor: {
        type: String,
        default: 'primary'
      },

      gutter: {
        type: String,
        validator: function (v) { return ['none', 'xs', 'sm', 'md', 'lg', 'xl'].includes(v); },
        default: 'sm'
      }
    },

    computed: {
      classes: function classes () {
        return ("" + (this.alignClass) + (this.gutter === 'none' ? '' : (" q-gutter-" + (this.gutter))))
      },

      sepClass: function sepClass () {
        if (this.separatorColor) {
          return ("text-" + (this.separatorColor))
        }
      },

      activeClass: function activeClass () {
        return ("text-" + (this.activeColor))
      }
    },

    render: function render (h) {
      var this$1 = this;

      var nodes = slot(this, 'default');
      if (nodes === void 0) { return }

      var els = 1;

      var
        child = [],
        len = nodes.filter(function (c) { return c.tag !== void 0 && c.tag.endsWith('-QBreadcrumbsEl'); }).length,
        separator = this.$scopedSlots.separator !== void 0
          ? this.$scopedSlots.separator
          : function () { return this$1.separator; };

      nodes.forEach(function (comp) {
        if (comp.tag !== void 0 && comp.tag.endsWith('-QBreadcrumbsEl')) {
          var middle = els < len;
          els++;

          child.push(h('div', {
            staticClass: 'flex items-center',
            class: middle ? this$1.activeClass : 'q-breadcrumbs--last'
          }, [ comp ]));

          if (middle) {
            child.push(h('div', {
              staticClass: 'q-breadcrumbs__separator', class: this$1.sepClass
            }, separator()));
          }
        }
        else {
          child.push(comp);
        }
      });

      return h('div', {
        staticClass: 'q-breadcrumbs',
        on: this.$listeners
      }, [
        h('div', {
          staticClass: 'flex items-center',
          class: this.classes
        }, child)
      ])
    }
  });

  var routerLinkProps = {
    to: [String, Object],
    exact: Boolean,
    append: Boolean,
    replace: Boolean,
    activeClass: String,
    exactActiveClass: String,
    disable: Boolean
  };

  var RouterLinkMixin = {
    props: routerLinkProps,

    computed: {
      hasRouterLink: function hasRouterLink () {
        return this.disable !== true && this.to !== void 0 && this.to !== null && this.to !== ''
      },

      routerLinkProps: function routerLinkProps () {
        return {
          to: this.to,
          exact: this.exact,
          append: this.append,
          replace: this.replace,
          activeClass: this.activeClass || 'q-router-link--active',
          exactActiveClass: this.exactActiveClass || 'q-router-link--exact-active',
          event: this.disable === true ? '' : void 0
        }
      }
    }
  };

  var QBreadcrumbsEl = Vue.extend({
    name: 'QBreadcrumbsEl',

    mixins: [ RouterLinkMixin ],

    props: {
      label: String,
      icon: String
    },

    render: function render (h) {
      var obj;

      var child = [];

      this.icon !== void 0 && child.push(
        h(QIcon, {
          staticClass: 'q-breadcrumbs__el-icon',
          class: this.label !== void 0 ? 'q-breadcrumbs__el-icon--with-label' : null,
          props: { name: this.icon }
        })
      );

      this.label && child.push(this.label);

      return h(this.hasRouterLink === true ? 'router-link' : 'span', ( obj = {
        staticClass: 'q-breadcrumbs__el q-link flex inline items-center relative-position',
        props: this.hasRouterLink === true ? this.routerLinkProps : null
      }, obj[this.hasRouterLink === true ? 'nativeOn' : 'on'] = this.$listeners, obj ), mergeSlot(child, this, 'default'))
    }
  });

  var mixin = {
    props: {
      color: String,
      size: {
        type: [Number, String],
        default: '1em'
      }
    },

    computed: {
      cSize: function cSize () {
        return this.size in sizes
          ? ((sizes[this.size]) + "px")
          : this.size
      },

      classes: function classes () {
        if (this.color) {
          return ("text-" + (this.color))
        }
      }
    }
  };

  var QSpinner = Vue.extend({
    name: 'QSpinner',

    mixins: [ mixin ],

    props: {
      thickness: {
        type: Number,
        default: 5
      }
    },

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner q-spinner-mat',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '25 25 50 50'
        }
      }, [
        h('circle', {
          staticClass: 'path',
          attrs: {
            'cx': '50',
            'cy': '50',
            'r': '20',
            'fill': 'none',
            'stroke': 'currentColor',
            'stroke-width': this.thickness,
            'stroke-miterlimit': '10'
          }
        })
      ])
    }
  });

  function offset (el) {
    if (el === window) {
      return { top: 0, left: 0 }
    }
    var ref = el.getBoundingClientRect();
    var top = ref.top;
    var left = ref.left;
    return { top: top, left: left }
  }

  function style (el, property) {
    return window.getComputedStyle(el).getPropertyValue(property)
  }

  function height (el) {
    return el === window
      ? window.innerHeight
      : el.getBoundingClientRect().height
  }

  function width (el) {
    return el === window
      ? window.innerWidth
      : el.getBoundingClientRect().width
  }

  function css (element, css) {
    var style = element.style;

    Object.keys(css).forEach(function (prop) {
      style[prop] = css[prop];
    });
  }

  function cssBatch (elements, style) {
    elements.forEach(function (el) { return css(el, style); });
  }

  function ready (fn) {
    if (typeof fn !== 'function') {
      return
    }

    if (document.readyState !== 'loading') {
      return fn()
    }

    document.addEventListener('DOMContentLoaded', fn, false);
  }

  function childHasFocus (el, focusedEl) {
    if (el === void 0 || el.contains(focusedEl) === true) {
      return true
    }

    for (var next = el.nextElementSibling; next !== null; next = next.nextElementSibling) {
      if (next.contains(focusedEl)) {
        return true
      }
    }

    return false
  }

  var dom = {
    offset: offset,
    style: style,
    height: height,
    width: width,
    css: css,
    cssBatch: cssBatch,
    ready: ready
  };

  function showRipple (evt, el, ctx, forceCenter) {
    ctx.modifiers.stop === true && stop(evt);

    var ref = ctx.modifiers;
    var center = ref.center;
    var color = ref.color;
    center = center === true || forceCenter === true;

    var
      node = document.createElement('span'),
      innerNode = document.createElement('span'),
      pos = position(evt);
    var ref$1 = el.getBoundingClientRect();
    var left = ref$1.left;
    var top = ref$1.top;
    var width = ref$1.width;
    var height = ref$1.height;
    var diameter = Math.sqrt(width * width + height * height),
      radius = diameter / 2,
      centerX = ((width - diameter) / 2) + "px",
      x = center ? centerX : ((pos.left - left - radius) + "px"),
      centerY = ((height - diameter) / 2) + "px",
      y = center ? centerY : ((pos.top - top - radius) + "px");

    innerNode.className = 'q-ripple__inner';
    css(innerNode, {
      height: (diameter + "px"),
      width: (diameter + "px"),
      transform: ("translate3d(" + x + "," + y + ",0) scale3d(.2,.2,1)"),
      opacity: 0
    });

    node.className = "q-ripple" + (color ? ' text-' + color : '');
    node.setAttribute('dir', 'ltr');
    node.appendChild(innerNode);
    el.appendChild(node);

    var abort = function () {
      node.remove();
      clearTimeout(timer);
    };
    ctx.abort.push(abort);

    var timer = setTimeout(function () {
      innerNode.classList.add('q-ripple__inner--enter');
      innerNode.style.transform = "translate3d(" + centerX + "," + centerY + ",0) scale3d(1,1,1)";
      innerNode.style.opacity = 0.2;

      timer = setTimeout(function () {
        innerNode.classList.remove('q-ripple__inner--enter');
        innerNode.classList.add('q-ripple__inner--leave');
        innerNode.style.opacity = 0;

        timer = setTimeout(function () {
          node.remove();
          ctx.abort.splice(ctx.abort.indexOf(abort), 1);
        }, 275);
      }, 250);
    }, 50);
  }

  function updateCtx (ctx, ref) {
    var value = ref.value;
    var modifiers = ref.modifiers;
    var arg = ref.arg;

    ctx.enabled = value !== false;

    if (ctx.enabled === true) {
      ctx.modifiers = Object(value) === value
        ? {
          stop: value.stop === true || modifiers.stop === true,
          center: value.center === true || modifiers.center === true,
          color: value.color || arg,
          keyCodes: [].concat(value.keyCodes || 13)
        }
        : {
          stop: modifiers.stop,
          center: modifiers.center,
          color: arg,
          keyCodes: [13]
        };
    }
  }

  var Ripple = {
    name: 'ripple',

    inserted: function inserted (el, binding) {
      var ctx = {
        modifiers: {},
        abort: [],

        click: function click (evt) {
          // on ENTER in form IE emits a PointerEvent with negative client cordinates
          if (
            ctx.enabled === true &&
            evt.qSkipRipple !== true &&
            (client.is.ie !== true || evt.clientX >= 0)
          ) {
            showRipple(evt, el, ctx, evt.qKeyEvent === true);
          }
        },

        keyup: function keyup (evt) {
          if (
            ctx.enabled === true &&
            evt.qSkipRipple !== true &&
            isKeyCode(evt, ctx.modifiers.keyCodes) === true
          ) {
            showRipple(evt, el, ctx, true);
          }
        }
      };

      updateCtx(ctx, binding);

      if (el.__qripple) {
        el.__qripple_old = el.__qripple;
      }

      el.__qripple = ctx;
      el.addEventListener('click', ctx.click, listenOpts.passive);
      el.addEventListener('keyup', ctx.keyup, listenOpts.passive);
    },

    update: function update (el, binding) {
      el.__qripple !== void 0 && updateCtx(el.__qripple, binding);
    },

    unbind: function unbind (el) {
      var ctx = el.__qripple_old || el.__qripple;
      if (ctx !== void 0) {
        ctx.abort.forEach(function (fn) { fn(); });
        el.removeEventListener('click', ctx.click, listenOpts.passive);
        el.removeEventListener('keyup', ctx.keyup, listenOpts.passive);
        delete el[el.__qripple_old ? '__qripple_old' : '__qripple'];
      }
    }
  };

  var RippleMixin = {
    directives: {
      Ripple: Ripple
    },

    props: {
      ripple: {
        type: [Boolean, Object],
        default: true
      }
    }
  };

  var BtnMixin = {
    mixins: [
      RippleMixin,
      AlignMixin,
      getSizeMixin({
        xs: 8,
        sm: 10,
        md: 14,
        lg: 20,
        xl: 24
      })
    ],

    props: {
      type: String,
      to: [Object, String],
      replace: Boolean,

      label: [Number, String],
      icon: String,
      iconRight: String,

      round: Boolean,
      outline: Boolean,
      flat: Boolean,
      unelevated: Boolean,
      rounded: Boolean,
      push: Boolean,
      glossy: Boolean,

      size: String,
      fab: Boolean,
      fabMini: Boolean,

      color: String,
      textColor: String,
      noCaps: Boolean,
      noWrap: Boolean,
      dense: Boolean,

      tabindex: [Number, String],

      align: { default: 'center' },
      stack: Boolean,
      stretch: Boolean,
      loading: {
        type: Boolean,
        default: null
      },
      disable: Boolean
    },

    computed: {
      style: function style () {
        if (this.fab === false && this.fabMini === false) {
          return this.sizeStyle
        }
      },

      isRounded: function isRounded () {
        return this.rounded === true || this.fab === true || this.fabMini === true
      },

      isActionable: function isActionable () {
        return this.disable !== true && this.loading !== true
      },

      computedTabIndex: function computedTabIndex () {
        return this.isActionable === true ? this.tabindex || 0 : -1
      },

      hasRouterLink: function hasRouterLink () {
        return this.disable !== true && this.to !== void 0 && this.to !== null && this.to !== ''
      },

      isLink: function isLink () {
        return this.type === 'a' || this.hasRouterLink === true
      },

      design: function design () {
        if (this.flat === true) { return 'flat' }
        if (this.outline === true) { return 'outline' }
        if (this.push === true) { return 'push' }
        if (this.unelevated === true) { return 'unelevated' }
        return 'standard'
      },

      attrs: function attrs () {
        var attrs = { tabindex: this.computedTabIndex };

        if (this.type !== 'a') {
          attrs.type = this.type || 'button';
        }

        if (this.hasRouterLink === true) {
          attrs.href = this.$router.resolve(this.to).href;
          attrs.role = 'link';
        }
        else {
          attrs.role = this.type === 'a' ? 'link' : 'button';
        }

        if (this.loading === true && this.percentage !== void 0) {
          attrs.role = 'progressbar';
          attrs['aria-valuemin'] = 0;
          attrs['aria-valuemax'] = 100;
          attrs['aria-valuenow'] = this.computedPercentage;
        }

        if (this.disable === true) {
          attrs.disabled = '';
          attrs['aria-disabled'] = '';
        }

        return attrs
      },

      classes: function classes () {
        var colors;

        if (this.color !== void 0) {
          if (this.flat === true || this.outline === true) {
            colors = "text-" + (this.textColor || this.color);
          }
          else {
            colors = "bg-" + (this.color) + " text-" + (this.textColor || 'white');
          }
        }
        else if (this.textColor) {
          colors = "text-" + (this.textColor);
        }

        return "q-btn--" + (this.design) + " " +
          "q-btn--" + (this.round === true ? 'round' : ("rectangle" + (this.isRounded === true ? ' q-btn--rounded' : ''))) +
          (colors !== void 0 ? ' ' + colors : '') +
          (this.isActionable === true ? ' q-btn--actionable q-focusable q-hoverable' : (this.disable === true ? ' disabled' : '')) +
          (this.fab === true ? ' q-btn--fab' : (this.fabMini === true ? ' q-btn--fab-mini' : '')) +
          (this.noCaps === true ? ' q-btn--no-uppercase' : '') +
          (this.noWrap === true ? '' : ' q-btn--wrap') + // this is for IE11
          (this.dense === true ? ' q-btn--dense' : '') +
          (this.stretch === true ? ' no-border-radius self-stretch' : '') +
          (this.glossy === true ? ' glossy' : '')
      },

      innerClasses: function innerClasses () {
        return this.alignClass + (this.stack === true ? ' column' : ' row') +
          (this.noWrap === true ? ' no-wrap text-no-wrap' : '') +
          (this.loading === true ? ' q-btn__content--hidden' : '')
      }
    }
  };

  var directions = [ 'left', 'right', 'up', 'down', 'horizontal', 'vertical' ];

  var modifiersAll = {
    left: true,
    right: true,
    up: true,
    down: true,
    horizontal: true,
    vertical: true,
    all: true
  };

  function getModifierDirections (mod) {
    var dir = {};

    directions.forEach(function (direction) {
      if (mod[direction]) {
        dir[direction] = true;
      }
    });

    if (Object.keys(dir).length === 0) {
      return modifiersAll
    }

    if (dir.horizontal === true) {
      dir.left = dir.right = true;
    }
    if (dir.vertical === true) {
      dir.up = dir.down = true;
    }
    if (dir.left === true && dir.right === true) {
      dir.horizontal = true;
    }
    if (dir.up === true && dir.down === true) {
      dir.vertical = true;
    }
    if (dir.horizontal === true && dir.vertical === true) {
      dir.all = true;
    }

    return dir
  }

  function updateModifiers (ctx, ref) {
    var oldValue = ref.oldValue;
    var value = ref.value;
    var modifiers = ref.modifiers;

    if (oldValue !== value) {
      typeof value !== 'function' && ctx.end();
      ctx.handler = value;
    }

    if (
      ctx.modifiers.mouseAllDir !== modifiers.mouseAllDir ||
      directions.some(function (direction) { return modifiers[direction] !== ctx.modifiers[direction]; })
    ) {
      ctx.modifiers = modifiers;
      ctx.direction = getModifierDirections(modifiers);
    }
  }

  function addEvt (ctx, target, events) {
    target += 'Evt';

    ctx[target] = ctx[target] !== void 0
      ? ctx[target].concat(events)
      : events;

    events.forEach(function (evt) {
      evt[0].addEventListener(evt[1], ctx[evt[2]], listenOpts[evt[3]]);
    });
  }

  function cleanEvt (ctx, target) {
    target += 'Evt';

    if (ctx[target] !== void 0) {
      ctx[target].forEach(function (evt) {
        evt[0].removeEventListener(evt[1], ctx[evt[2]], listenOpts[evt[3]]);
      });
      ctx[target] = void 0;
    }
  }

  var getTouchTarget = isSSR === false && iosEmulated !== true && (
    client.is.ios === true ||
    window.navigator.vendor.toLowerCase().indexOf('apple') > -1
  )
    ? function () { return document; }
    : function (target) { return target; };

  function shouldStart (evt, ctx) {
    return ctx.event === void 0 &&
      evt.target !== void 0 &&
      evt.target.draggable !== true &&
      typeof ctx.handler === 'function' &&
      evt.target.nodeName.toUpperCase() !== 'INPUT' &&
      (evt.qClonedBy === void 0 || evt.qClonedBy.indexOf(ctx.uid) === -1)
  }

  var passiveCapture = listenOpts.passiveCapture;

  var
    touchTarget = void 0,
    keyboardTarget = void 0,
    mouseTarget = void 0;

  var iconAttrs = { role: 'img', 'aria-hidden': 'true' };

  var QBtn = Vue.extend({
    name: 'QBtn',

    mixins: [ BtnMixin ],

    props: {
      percentage: Number,
      darkPercentage: Boolean
    },

    computed: {
      hasLabel: function hasLabel () {
        return this.label !== void 0 && this.label !== null && this.label !== ''
      },

      computedRipple: function computedRipple () {
        return this.ripple === false
          ? false
          : Object.assign(
            { keyCodes: [] },
            this.ripple === true ? {} : this.ripple
          )
      },

      percentageStyle: function percentageStyle () {
        var val = Math.max(0, Math.min(100, this.percentage));
        if (val > 0) {
          return { transition: 'transform 0.6s', transform: ("translateX(" + (val - 100) + "%)") }
        }
      }
    },

    methods: {
      click: function click (e) {
        var this$1 = this;

        if (e !== void 0) {
          if (e.defaultPrevented === true) {
            return
          }

          var el = document.activeElement;
          // focus button if it came from ENTER on form
          // prevent the new submit (already done)
          if (
            this.type === 'submit' &&
            (
              (this.$q.platform.is.ie === true && (e.clientX < 0 || e.clientY < 0)) ||
              (
                el !== document.body &&
                this.$el.contains(el) === false &&
                // required for iOS and desktop Safari
                el.contains(this.$el) === false
              )
            )
          ) {
            this.$el.focus();

            var onClickCleanup = function () {
              document.removeEventListener('keydown', stopAndPrevent, true);
              document.removeEventListener('keyup', onClickCleanup, passiveCapture);
              this$1.$el !== void 0 && this$1.$el.removeEventListener('blur', onClickCleanup, passiveCapture);
            };

            document.addEventListener('keydown', stopAndPrevent, true);
            document.addEventListener('keyup', onClickCleanup, passiveCapture);
            this.$el.addEventListener('blur', onClickCleanup, passiveCapture);
          }

          if (this.hasRouterLink === true) {
            if (
              e.ctrlKey === true ||
              e.shiftKey === true ||
              e.altKey === true ||
              e.metaKey === true
            ) {
              // if it has meta keys, let vue-router link
              // handle this by its own
              return
            }

            stopAndPrevent(e);
          }
        }

        var go = function () {
          var res = this$1.$router[this$1.replace === true ? 'replace' : 'push'](this$1.to);

          // vue-router now throwing error if navigating
          // to the same route that the user is currently at
          // https://github.com/vuejs/vue-router/issues/2872
          if (res !== void 0 && typeof res.catch === 'function') {
            res.catch(noop);
          }
        };

        this.$emit('click', e, go);
        this.hasRouterLink === true && e.navigate !== false && go();
      },

      __onKeydown: function __onKeydown (e) {
        if (isKeyCode(e, [ 13, 32 ]) === true) {
          stopAndPrevent(e);

          if (keyboardTarget !== this.$el) {
            keyboardTarget !== void 0 && this.__cleanup();

            // focus external button if the focus helper was focused before
            this.$el.focus();

            keyboardTarget = this.$el;
            this.$el.classList.add('q-btn--active');
            document.addEventListener('keyup', this.__onPressEnd, true);
            this.$el.addEventListener('blur', this.__onPressEnd, passiveCapture);
          }
        }

        this.$emit('keydown', e);
      },

      __onTouchstart: function __onTouchstart (e) {
        if (touchTarget !== this.$el) {
          touchTarget !== void 0 && this.__cleanup();
          touchTarget = this.$el;
          var target = this.touchTargetEl = getTouchTarget(e.target);
          target.addEventListener('touchcancel', this.__onPressEnd, passiveCapture);
          target.addEventListener('touchend', this.__onPressEnd, passiveCapture);
        }

        this.$emit('touchstart', e);
      },

      __onMousedown: function __onMousedown (e) {
        if (mouseTarget !== this.$el) {
          mouseTarget !== void 0 && this.__cleanup();
          mouseTarget = this.$el;
          this.$el.classList.add('q-btn--active');
          document.addEventListener('mouseup', this.__onPressEnd, passiveCapture);
        }

        this.$emit('mousedown', e);
      },

      __onPressEnd: function __onPressEnd (e) {
        // needed for IE (because it emits blur when focusing button from focus helper)
        if (e !== void 0 && e.type === 'blur' && document.activeElement === this.$el) {
          return
        }

        if (e !== void 0 && e.type === 'keyup') {
          if (keyboardTarget === this.$el && isKeyCode(e, [ 13, 32 ]) === true) {
            // for click trigger
            var evt = new MouseEvent('click', e);
            evt.qKeyEvent = true;
            e.defaultPrevented === true && prevent(evt);
            e.cancelBubble === true && stop(evt);
            this.$el.dispatchEvent(evt);

            stopAndPrevent(e);

            // for ripple
            e.qKeyEvent = true;
          }

          this.$emit('keyup', e);
        }

        this.__cleanup();
      },

      __cleanup: function __cleanup (destroying) {
        if (
          destroying !== true &&
          (touchTarget === this.$el || mouseTarget === this.$el) &&
          this.$refs.blurTarget !== void 0 &&
          this.$refs.blurTarget !== document.activeElement
        ) {
          this.$refs.blurTarget.focus();
        }

        if (touchTarget === this.$el) {
          var target = this.touchTargetEl;
          target.removeEventListener('touchcancel', this.__onPressEnd, passiveCapture);
          target.removeEventListener('touchend', this.__onPressEnd, passiveCapture);
          touchTarget = this.touchTargetEl = void 0;
        }

        if (mouseTarget === this.$el) {
          document.removeEventListener('mouseup', this.__onPressEnd, passiveCapture);
          mouseTarget = void 0;
        }

        if (keyboardTarget === this.$el) {
          document.removeEventListener('keyup', this.__onPressEnd, true);
          this.$el !== void 0 && this.$el.removeEventListener('blur', this.__onPressEnd, passiveCapture);
          keyboardTarget = void 0;
        }

        this.$el !== void 0 && this.$el.classList.remove('q-btn--active');
      },

      __onLoadingEvt: function __onLoadingEvt (evt) {
        stopAndPrevent(evt);
        evt.qSkipRipple = true;
      }
    },

    beforeDestroy: function beforeDestroy () {
      this.__cleanup(true);
    },

    render: function render (h) {
      var inner = [];
      var data = {
        staticClass: 'q-btn q-btn-item non-selectable no-outline',
        class: this.classes,
        style: this.style,
        attrs: this.attrs
      };

      if (this.isActionable === true) {
        data.on = Object.assign({}, this.$listeners,
          {click: this.click,
          keydown: this.__onKeydown,
          mousedown: this.__onMousedown});

        if (this.$q.platform.has.touch === true) {
          data.on.touchstart = this.__onTouchstart;
        }
      }

      if (this.disable !== true && this.ripple !== false) {
        data.directives = [{
          name: 'ripple',
          value: this.computedRipple,
          modifiers: { center: this.round }
        }];
      }

      this.icon !== void 0 && inner.push(
        h(QIcon, {
          attrs: iconAttrs,
          props: { name: this.icon, left: this.stack === false && this.hasLabel === true }
        })
      );

      this.hasLabel === true && inner.push(
        h('div', [ this.label ])
      );

      inner = mergeSlot(inner, this, 'default');

      if (this.iconRight !== void 0 && this.round === false) {
        inner.push(
          h(QIcon, {
            attrs: iconAttrs,
            props: { name: this.iconRight, right: this.stack === false && this.hasLabel === true }
          })
        );
      }

      var child = [
        h('div', {
          staticClass: 'q-focus-helper',
          ref: 'blurTarget',
          attrs: { tabindex: -1 }
        })
      ];

      if (this.loading === true) {
        // stop propagation and ripple
        data.on = {
          click: this.__onLoadingEvt,
          keyup: this.__onLoadingEvt
        };

        this.percentage !== void 0 && child.push(
          h('div', {
            staticClass: 'q-btn__progress absolute-full overflow-hidden'
          }, [
            h('div', {
              staticClass: 'q-btn__progress-indicator fit',
              class: this.darkPercentage === true ? 'q-btn__progress--dark' : '',
              style: this.percentageStyle
            })
          ])
        );
      }

      child.push(
        h('div', {
          staticClass: 'q-btn__wrapper col row q-anchor--skip'
        }, [
          h('div', {
            staticClass: 'q-btn__content text-center col items-center q-anchor--skip',
            class: this.innerClasses
          }, inner)
        ])
      );

      this.loading !== null && child.push(
        h('transition', {
          props: { name: 'q-transition--fade' }
        }, this.loading === true ? [
          h('div', {
            key: 'loading',
            staticClass: 'absolute-full flex flex-center'
          }, this.$scopedSlots.loading !== void 0 ? this.$scopedSlots.loading() : [ h(QSpinner) ])
        ] : void 0)
      );

      return h(this.isLink === true ? 'a' : 'button', data, child)
    }
  });

  var QBtnGroup = Vue.extend({
    name: 'QBtnGroup',

    props: {
      unelevated: Boolean,
      outline: Boolean,
      flat: Boolean,
      rounded: Boolean,
      push: Boolean,
      stretch: Boolean,
      glossy: Boolean,
      spread: Boolean
    },

    computed: {
      classes: function classes () {
        var this$1 = this;

        return ['unelevated', 'outline', 'flat', 'rounded', 'push', 'stretch', 'glossy']
          .filter(function (t) { return this$1[t] === true; })
          .map(function (t) { return ("q-btn-group--" + t); }).join(' ')
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-btn-group row no-wrap ' +
          (this.spread === true ? 'q-btn-group--spread' : 'inline'),
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  function clearSelection () {
    if (window.getSelection !== void 0) {
      var selection = window.getSelection();
      if (selection.empty !== void 0) {
        selection.empty();
      }
      else if (selection.removeAllRanges !== void 0) {
        selection.removeAllRanges();
        Platform.is.mobile !== true && selection.addRange(document.createRange());
      }
    }
    else if (document.selection !== void 0) {
      document.selection.empty();
    }
  }

  var AnchorMixin = {
    props: {
      target: {
        default: true
      },
      noParentEvent: Boolean,
      contextMenu: Boolean
    },

    watch: {
      contextMenu: function contextMenu (val) {
        if (this.anchorEl !== void 0) {
          this.__unconfigureAnchorEl();
          this.__configureAnchorEl(val);
        }
      },

      target: function target () {
        if (this.anchorEl !== void 0) {
          this.__unconfigureAnchorEl();
        }

        this.__pickAnchorEl();
      },

      noParentEvent: function noParentEvent (val) {
        if (this.anchorEl !== void 0) {
          if (val === true) {
            this.__unconfigureAnchorEl();
          }
          else {
            this.__configureAnchorEl();
          }
        }
      }
    },

    methods: {
      __showCondition: function __showCondition (evt) {
        // abort with no parent configured or on multi-touch
        if (this.anchorEl === void 0) {
          return false
        }
        if (evt === void 0) {
          return true
        }
        return evt.touches === void 0 || evt.touches.length <= 1
      },

      __contextClick: function __contextClick (evt) {
        var this$1 = this;

        this.hide(evt);
        this.$nextTick(function () {
          this$1.show(evt);
        });
        prevent(evt);
      },

      __toggleKey: function __toggleKey (evt) {
        isKeyCode(evt, 13) === true && this.toggle(evt);
      },

      __mobileCleanup: function __mobileCleanup (evt) {
        this.anchorEl.classList.remove('non-selectable');
        clearTimeout(this.touchTimer);

        if (this.showing === true && evt !== void 0) {
          clearSelection();
        }
      },

      __mobilePrevent: prevent,

      __mobileTouch: function __mobileTouch (evt) {
        var this$1 = this;

        this.__mobileCleanup(evt);

        if (this.__showCondition(evt) !== true) {
          return
        }

        this.hide(evt);
        this.anchorEl.classList.add('non-selectable');

        var target = getTouchTarget(evt.target);
        addEvt(this, 'anchor', [
          [ target, 'touchmove', '__mobileCleanup', 'passive' ],
          [ target, 'touchend', '__mobileCleanup', 'passive' ],
          [ target, 'touchcancel', '__mobileCleanup', 'passive' ],
          [ this.anchorEl, 'contextmenu', '__mobilePrevent', 'notPassive' ]
        ]);

        this.touchTimer = setTimeout(function () {
          this$1.show(evt);
        }, 300);
      },

      __unconfigureAnchorEl: function __unconfigureAnchorEl () {
        cleanEvt(this, 'anchor');
      },

      __configureAnchorEl: function __configureAnchorEl (context) {
        if ( context === void 0 ) context = this.contextMenu;

        if (this.noParentEvent === true || this.anchorEl === void 0) { return }

        var evts;

        if (context === true) {
          if (this.$q.platform.is.mobile === true) {
            evts = [
              [ this.anchorEl, 'touchstart', '__mobileTouch', 'passive' ]
            ];
          }
          else {
            evts = [
              [ this.anchorEl, 'click', 'hide', 'passive' ],
              [ this.anchorEl, 'contextmenu', '__contextClick', 'notPassive' ]
            ];
          }
        }
        else {
          evts = [
            [ this.anchorEl, 'click', 'toggle', 'passive' ],
            [ this.anchorEl, 'keyup', '__toggleKey', 'passive' ]
          ];
        }

        addEvt(this, 'anchor', evts);
      },

      __setAnchorEl: function __setAnchorEl (el) {
        this.anchorEl = el;
        while (this.anchorEl.classList.contains('q-anchor--skip')) {
          this.anchorEl = this.anchorEl.parentNode;
        }
        this.__configureAnchorEl();
      },

      __pickAnchorEl: function __pickAnchorEl () {
        if (this.target === false || this.target === '') {
          this.anchorEl = void 0;
        }
        else if (this.target === true) {
          this.__setAnchorEl(this.parentEl);
        }
        else {
          var el = this.target;

          if (typeof this.target === 'string') {
            try {
              el = document.querySelector(this.target);
            }
            catch (err) {
              el = void 0;
            }
          }

          if (el !== void 0 && el !== null) {
            this.anchorEl = el._isVue === true && el.$el !== void 0 ? el.$el : el;
            this.__configureAnchorEl();
          }
          else {
            this.anchorEl = void 0;
            console.error(("Anchor: target \"" + (this.target) + "\" not found"), this);
          }
        }
      },

      __changeScrollEvent: function __changeScrollEvent (scrollTarget, fn) {
        var fnProp = (fn !== void 0 ? 'add' : 'remove') + "EventListener";
        var fnHandler = fn !== void 0 ? fn : this.__scrollFn;

        if (scrollTarget !== window) {
          scrollTarget[fnProp]('scroll', fnHandler, listenOpts.passive);
        }

        window[fnProp]('scroll', fnHandler, listenOpts.passive);

        this.__scrollFn = fn;
      }
    },

    created: function created () {
      var this$1 = this;

      if (
        typeof this.__configureScrollTarget === 'function' &&
        typeof this.__unconfigureScrollTarget === 'function'
      ) {
        this.noParentEventWatcher = this.$watch('noParentEvent', function () {
          if (this$1.__scrollTarget !== void 0) {
            this$1.__unconfigureScrollTarget();
            this$1.__configureScrollTarget();
          }
        });
      }
    },

    mounted: function mounted () {
      this.parentEl = this.$el.parentNode;
      this.__pickAnchorEl();

      if (this.value === true && this.anchorEl === void 0) {
        this.$emit('input', false);
      }
    },

    beforeDestroy: function beforeDestroy () {
      clearTimeout(this.touchTimer);
      this.noParentEventWatcher !== void 0 && this.noParentEventWatcher();
      this.__anchorCleanup !== void 0 && this.__anchorCleanup();
      this.__unconfigureAnchorEl();
    }
  };

  var TimeoutMixin = {
    methods: {
      __nextTick: function __nextTick (fn) {
        this.__tickFn = fn;
      },

      __prepareTick: function __prepareTick () {
        var this$1 = this;

        if (this.__tickFn !== void 0) {
          var fn = this.__tickFn;
          this.$nextTick(function () {
            if (this$1.__tickFn === fn) {
              this$1.__tickFn();
              this$1.__tickFn = void 0;
            }
          });
        }
      },

      __clearTick: function __clearTick () {
        this.__tickFn = void 0;
      },

      __setTimeout: function __setTimeout (fn, delay) {
        clearTimeout(this.__timer);
        this.__timer = setTimeout(fn, delay);
      },

      __clearTimeout: function __clearTimeout () {
        clearTimeout(this.__timer);
      }
    },

    beforeDestroy: function beforeDestroy () {
      this.__tickFn = void 0;
      clearTimeout(this.__timer);
    }
  };

  var ModelToggleMixin = {
    mixins: [ TimeoutMixin ],

    props: {
      value: {
        type: Boolean,
        default: void 0
      }
    },

    data: function data () {
      return {
        showing: false
      }
    },

    watch: {
      value: function value (val) {
        this.__processModelChange(val);
      },

      $route: function $route () {
        this.hideOnRouteChange === true && this.showing === true && this.hide();
      }
    },

    methods: {
      toggle: function toggle (evt) {
        this[this.showing === true ? 'hide' : 'show'](evt);
      },

      show: function show (evt) {
        var this$1 = this;

        if (this.disable === true || (this.__showCondition !== void 0 && this.__showCondition(evt) !== true)) {
          return
        }

        if (this.$listeners.input !== void 0 && isSSR === false) {
          this.$emit('input', true);
          this.payload = evt;
          this.$nextTick(function () {
            if (this$1.payload === evt) {
              this$1.payload = void 0;
            }
          });
        }
        if (this.value === void 0 || this.$listeners.input === void 0 || isSSR === true) {
          this.__processShow(evt);
        }
      },

      __processShow: function __processShow (evt) {
        if (this.showing === true) {
          return
        }

        // need to call it before setting showing to true
        // in order to not ruin the animation
        this.__preparePortal !== void 0 && this.__preparePortal();

        this.showing = true;

        this.$emit('before-show', evt);

        if (this.__show !== void 0) {
          this.__clearTick();
          this.__show(evt);
          this.__prepareTick();
        }
        else {
          this.$emit('show', evt);
        }
      },

      hide: function hide (evt) {
        var this$1 = this;

        if (this.disable === true) {
          return
        }

        if (this.$listeners.input !== void 0 && isSSR === false) {
          this.$emit('input', false);
          this.payload = evt;
          this.$nextTick(function () {
            if (this$1.payload === evt) {
              this$1.payload = void 0;
            }
          });
        }
        if (this.value === void 0 || this.$listeners.input === void 0 || isSSR === true) {
          this.__processHide(evt);
        }
      },

      __processHide: function __processHide (evt) {
        if (this.showing === false) {
          return
        }

        this.showing = false;

        this.$emit('before-hide', evt);

        if (this.__hide !== void 0) {
          this.__clearTick();
          this.__hide(evt);
          this.__prepareTick();
        }
        else {
          this.$emit('hide', evt);
        }
      },

      __processModelChange: function __processModelChange (val) {
        if (this.disable === true && val === true) {
          this.$listeners.input !== void 0 && this.$emit('input', false);
        }
        else if ((val === true) !== this.showing) {
          this[("__process" + (val === true ? 'Show' : 'Hide'))](this.payload);
        }
      }
    }
  };

  function closePortalMenus (vm, evt) {
    do {
      if (vm.$options.name === 'QMenu') {
        vm.hide(evt);

        // is this a point of separation?
        if (vm.separateClosePopup === true) {
          return vm.$parent
        }
      }
      else if (vm.__renderPortal !== void 0) {
        // treat it as point of separation if parent is QPopupProxy
        // (so mobile matches desktop behavior)
        // and hide it too
        if (vm.$parent !== void 0 && vm.$parent.$options.name === 'QPopupProxy') {
          vm.hide(evt);
          return vm.$parent
        }
        else {
          return vm
        }
      }
      vm = vm.$parent;
    } while (vm !== void 0)
  }

  function closePortals (vm, evt, depth) {
    while (depth !== 0 && vm !== void 0) {
      if (vm.__renderPortal !== void 0) {
        depth--;

        if (vm.$options.name === 'QMenu') {
          vm = closePortalMenus(vm, evt);
          continue
        }

        vm.hide(evt);
      }

      vm = vm.$parent;
    }
  }

  var PortalMixin = {
    inheritAttrs: false,

    props: {
      contentClass: [Array, String, Object],
      contentStyle: [Array, String, Object]
    },

    methods: {
      __showPortal: function __showPortal () {
        if (this.__portal !== void 0) {
          document.body.appendChild(this.__portal.$el);
        }
      },

      __hidePortal: function __hidePortal () {
        if (this.__portal !== void 0) {
          this.__portal.$destroy();
          this.__portal.$el.remove();
          this.__portal = void 0;
        }
      },

      __preparePortal: function __preparePortal () {
        var this$1 = this;

        if (this.__portal === void 0) {
          this.__portal = new Vue({
            name: 'QPortal',
            parent: this,

            inheritAttrs: false,

            render: function (h) { return this$1.__renderPortal(h); },

            components: this.$options.components,
            directives: this.$options.directives
          }).$mount();
        }
      }
    },

    render: function render () {
      this.__portal !== void 0 && this.__portal.$forceUpdate();
    },

    beforeDestroy: function beforeDestroy () {
      this.__hidePortal();
    }
  };

  var TransitionMixin = {
    props: {
      transitionShow: {
        type: String,
        default: 'fade'
      },

      transitionHide: {
        type: String,
        default: 'fade'
      }
    },

    data: function data () {
      return {
        transitionState: this.showing
      }
    },

    watch: {
      showing: function showing (val) {
        var this$1 = this;

        this.transitionShow !== this.transitionHide && this.$nextTick(function () {
          this$1.transitionState = val;
        });
      }
    },

    computed: {
      transition: function transition () {
        return 'q-transition--' + (this.transitionState === true ? this.transitionHide : this.transitionShow)
      }
    }
  };

  function getAllChildren (vm, children) {
    if ( children === void 0 ) children = [];

    vm.$children.forEach(function (child) {
      children.push(child);
      child.$children.length > 0 && getAllChildren(child, children);
    });
    return children
  }

  function getVmOfNode (el) {
    for (var node = el; node !== null; node = node.parentNode) {
      // node.__vue__ can be null if the instance was destroyed
      if (node.__vue__ === null) {
        return
      }
      if (node.__vue__ !== void 0) {
        return node.__vue__
      }
    }
  }

  function isVmChildOf (childVm, parentVm) {
    for (var vm = childVm; vm !== void 0; vm = vm.$parent) {
      if (vm === parentVm) {
        return true
      }
    }
    return false
  }

  function cache (vm, key, obj) {
    if (isSSR === true) { return obj }

    var k = "__qcache_" + key;
    return vm[k] === void 0
      ? (vm[k] = obj)
      : vm[k]
  }

  var timer;

  var notPassiveCapture = listenOpts.notPassiveCapture;
  var passiveCapture$1 = listenOpts.passiveCapture;
  var handlers = {
      click: [],
      focus: []
    };

  function execHandlers (list, evt) {
    for (var i = list.length - 1; i >= 0; i--) {
      if (list[i](evt) === void 0) {
        return
      }
    }
  }

  function globalHandler (evt) {
    clearTimeout(timer);

    // prevent autofocus on body resulting from blur
    if (evt.type === 'focusin' && evt.target.hasAttribute('tabindex') === true) {
      timer = setTimeout(function () {
        execHandlers(handlers.focus, evt);
      }, 200);
    }
    else {
      execHandlers(handlers.click, evt);
    }
  }

  var ClickOutside = {
    name: 'click-outside',

    bind: function bind (el, ref, vnode) {
      var value = ref.value;
      var arg = ref.arg;

      var vmEl = vnode.componentInstance || vnode.context;

      var ctx = {
        trigger: value,
        toggleEl: arg,

        handler: function handler (evt) {
          var target = evt.target;

          if (
            target !== void 0 &&
            target.nodeType !== 8 &&
            // directives that prevent click by using pointer-events none generate click on html element
            target !== document.documentElement &&
            target.classList.contains('no-pointer-events') === false &&
            (
              ctx.toggleEl === void 0 ||
              ctx.toggleEl.contains(target) === false
            ) &&
            (
              target === document.body ||
              isVmChildOf(getVmOfNode(target), vmEl) === false
            )
          ) {
            // mark the event as beeing processed by clickOutside
            // used to prevent refocus after menu close
            evt.qClickOutside = true;

            return ctx.trigger(evt)
          }
        }
      };

      if (el.__qclickoutside) {
        el.__qclickoutside_old = el.__qclickoutside;
      }

      el.__qclickoutside = ctx;

      if (handlers.click.length === 0) {
        document.addEventListener('mousedown', globalHandler, notPassiveCapture);
        document.addEventListener('touchstart', globalHandler, notPassiveCapture);
        document.addEventListener('focusin', globalHandler, passiveCapture$1);
      }

      handlers.click.push(ctx.handler);

      ctx.timerFocusin = setTimeout(function () {
        handlers.focus.push(ctx.handler);
      }, 500);
    },

    update: function update (el, ref) {
      var value = ref.value;
      var oldValue = ref.oldValue;
      var arg = ref.arg;

      var ctx = el.__qclickoutside;

      if (value !== oldValue) {
        ctx.trigger = value;
      }
      if (arg !== ctx.arg) {
        ctx.toggleEl = arg;
      }
    },

    unbind: function unbind (el) {
      var ctx = el.__qclickoutside_old || el.__qclickoutside;
      if (ctx !== void 0) {
        clearTimeout(ctx.timerFocusin);

        var
          indexClick = handlers.click.findIndex(function (h) { return h === ctx.handler; }),
          indexFocus = handlers.focus.findIndex(function (h) { return h === ctx.handler; });

        indexClick > -1 && handlers.click.splice(indexClick, 1);
        indexFocus > -1 && handlers.focus.splice(indexFocus, 1);

        if (handlers.click.length === 0) {
          clearTimeout(timer);
          document.removeEventListener('mousedown', globalHandler, notPassiveCapture);
          document.removeEventListener('touchstart', globalHandler, notPassiveCapture);
          document.removeEventListener('focusin', globalHandler, passiveCapture$1);
        }

        delete el[el.__qclickoutside_old ? '__qclickoutside_old' : '__qclickoutside'];
      }
    }
  };

  var scrollTargets = isSSR === false
    ? [ null, document, document.body, document.scrollingElement, document.documentElement ]
    : [];

  function getScrollTarget (el, target) {
    if (typeof target === 'string') {
      try {
        target = document.querySelector(target);
      }
      catch (err) {
        target = void 0;
      }
    }

    if (target === void 0 || target === null) {
      target = el.closest('.scroll,.scroll-y,.overflow-auto');
    }
    else if (target._isVue === true && target.$el !== void 0) {
      target = target.$el;
    }

    return scrollTargets.includes(target)
      ? window
      : target
  }

  function getScrollHeight (el) {
    return (el === window ? document.body : el).scrollHeight
  }

  function getScrollWidth (el) {
    return (el === window ? document.body : el).scrollWidth
  }

  function getScrollPosition (scrollTarget) {
    if (scrollTarget === window) {
      return window.pageYOffset || window.scrollY || document.body.scrollTop || 0
    }
    return scrollTarget.scrollTop
  }

  function getHorizontalScrollPosition (scrollTarget) {
    if (scrollTarget === window) {
      return window.pageXOffset || window.scrollX || document.body.scrollLeft || 0
    }
    return scrollTarget.scrollLeft
  }

  function animScrollTo (el, to, duration) {
    if ( duration === void 0 ) duration = 0;

    var pos = getScrollPosition(el);

    if (duration <= 0) {
      if (pos !== to) {
        setScroll(el, to);
      }
      return
    }

    requestAnimationFrame(function () {
      var newPos = pos + (to - pos) / Math.max(16, duration) * 16;
      setScroll(el, newPos);
      if (newPos !== to) {
        animScrollTo(el, to, duration - 16);
      }
    });
  }

  function animHorizontalScrollTo (el, to, duration) {
    if ( duration === void 0 ) duration = 0;

    var pos = getHorizontalScrollPosition(el);

    if (duration <= 0) {
      if (pos !== to) {
        setHorizontalScroll(el, to);
      }
      return
    }

    requestAnimationFrame(function () {
      var newPos = pos + (to - pos) / Math.max(16, duration) * 16;
      setHorizontalScroll(el, newPos);
      if (newPos !== to) {
        animHorizontalScrollTo(el, to, duration - 16);
      }
    });
  }

  function setScroll (scrollTarget, offset) {
    if (scrollTarget === window) {
      window.scrollTo(window.pageXOffset || window.scrollX || document.body.scrollLeft || 0, offset);
      return
    }
    scrollTarget.scrollTop = offset;
  }

  function setHorizontalScroll (scrollTarget, offset) {
    if (scrollTarget === window) {
      window.scrollTo(offset, window.pageYOffset || window.scrollY || document.body.scrollTop || 0);
      return
    }
    scrollTarget.scrollLeft = offset;
  }

  function setScrollPosition (scrollTarget, offset, duration) {
    if (duration) {
      animScrollTo(scrollTarget, offset, duration);
      return
    }
    setScroll(scrollTarget, offset);
  }

  function setHorizontalScrollPosition (scrollTarget, offset, duration) {
    if (duration) {
      animHorizontalScrollTo(scrollTarget, offset, duration);
      return
    }
    setHorizontalScroll(scrollTarget, offset);
  }

  var size;
  function getScrollbarWidth () {
    if (size !== undefined) {
      return size
    }

    var
      inner = document.createElement('p'),
      outer = document.createElement('div');

    css(inner, {
      width: '100%',
      height: '200px'
    });
    css(outer, {
      position: 'absolute',
      top: '0px',
      left: '0px',
      visibility: 'hidden',
      width: '200px',
      height: '150px',
      overflow: 'hidden'
    });

    outer.appendChild(inner);

    document.body.appendChild(outer);

    var w1 = inner.offsetWidth;
    outer.style.overflow = 'scroll';
    var w2 = inner.offsetWidth;

    if (w1 === w2) {
      w2 = outer.clientWidth;
    }

    outer.remove();
    size = w1 - w2;

    return size
  }

  function hasScrollbar (el, onY) {
    if ( onY === void 0 ) onY = true;

    if (!el || el.nodeType !== Node.ELEMENT_NODE) {
      return false
    }

    return onY
      ? (
        el.scrollHeight > el.clientHeight && (
          el.classList.contains('scroll') ||
          el.classList.contains('overflow-auto') ||
          ['auto', 'scroll'].includes(window.getComputedStyle(el)['overflow-y'])
        )
      )
      : (
        el.scrollWidth > el.clientWidth && (
          el.classList.contains('scroll') ||
          el.classList.contains('overflow-auto') ||
          ['auto', 'scroll'].includes(window.getComputedStyle(el)['overflow-x'])
        )
      )
  }

  var scroll = {
    getScrollTarget: getScrollTarget,

    getScrollHeight: getScrollHeight,
    getScrollWidth: getScrollWidth,

    getScrollPosition: getScrollPosition,
    getHorizontalScrollPosition: getHorizontalScrollPosition,

    animScrollTo: animScrollTo,
    animHorizontalScrollTo: animHorizontalScrollTo,

    setScrollPosition: setScrollPosition,
    setHorizontalScrollPosition: setHorizontalScrollPosition,

    getScrollbarWidth: getScrollbarWidth,
    hasScrollbar: hasScrollbar
  };

  var handlers$1 = [];

  var EscapeKey = {
    __install: function __install () {
      this.__installed = true;
      window.addEventListener('keyup', function (evt) {
        if (handlers$1.length !== 0 && isKeyCode(evt, 27) === true) {
          handlers$1[handlers$1.length - 1].fn(evt);
        }
      });
    },

    register: function register (comp, fn) {
      if (comp.$q.platform.is.desktop === true) {
        this.__installed !== true && this.__install();
        handlers$1.push({ comp: comp, fn: fn });
      }
    },

    pop: function pop (comp) {
      if (comp.$q.platform.is.desktop === true) {
        var index = handlers$1.findIndex(function (h) { return h.comp === comp; });
        if (index > -1) {
          handlers$1.splice(index, 1);
        }
      }
    }
  };

  var vpLeft, vpTop;

  function validatePosition (pos) {
    var parts = pos.split(' ');
    if (parts.length !== 2) {
      return false
    }
    if (!['top', 'center', 'bottom'].includes(parts[0])) {
      console.error('Anchor/Self position must start with one of top/center/bottom');
      return false
    }
    if (!['left', 'middle', 'right'].includes(parts[1])) {
      console.error('Anchor/Self position must end with one of left/middle/right');
      return false
    }
    return true
  }

  function validateOffset (val) {
    if (!val) { return true }
    if (val.length !== 2) { return false }
    if (typeof val[0] !== 'number' || typeof val[1] !== 'number') {
      return false
    }
    return true
  }

  function parsePosition (pos) {
    var parts = pos.split(' ');
    return { vertical: parts[0], horizontal: parts[1] }
  }

  function getAnchorProps (el, offset) {
    var ref = el.getBoundingClientRect();
    var top = ref.top;
    var left = ref.left;
    var right = ref.right;
    var bottom = ref.bottom;
    var width = ref.width;
    var height = ref.height;

    if (offset !== void 0) {
      top -= offset[1];
      left -= offset[0];
      bottom += offset[1];
      right += offset[0];

      width += offset[0];
      height += offset[1];
    }

    return {
      top: top,
      left: left,
      right: right,
      bottom: bottom,
      width: width,
      height: height,
      middle: left + (right - left) / 2,
      center: top + (bottom - top) / 2
    }
  }

  function getTargetProps (el) {
    return {
      top: 0,
      center: el.offsetHeight / 2,
      bottom: el.offsetHeight,
      left: 0,
      middle: el.offsetWidth / 2,
      right: el.offsetWidth
    }
  }

  // cfg: { el, anchorEl, anchorOrigin, selfOrigin, offset, absoluteOffset, cover, fit, maxHeight, maxWidth }
  function setPosition (cfg) {
    if (client.is.ios === true && window.visualViewport !== void 0) {
      // uses the q-position-engine CSS class

      var el = document.body.style;
      var ref = window.visualViewport;
      var left = ref.offsetLeft;
      var top = ref.offsetTop;

      if (left !== vpLeft) {
        el.setProperty('--q-pe-left', left + 'px');
        vpLeft = left;
      }
      if (top !== vpTop) {
        el.setProperty('--q-pe-top', top + 'px');
        vpTop = top;
      }
    }

    var anchorProps;

    // scroll position might change
    // if max-height/-width changes, so we
    // need to restore it after we calculate
    // the new positioning
    var ref$1 = cfg.el;
    var scrollLeft = ref$1.scrollLeft;
    var scrollTop = ref$1.scrollTop;

    if (cfg.absoluteOffset === void 0) {
      anchorProps = getAnchorProps(cfg.anchorEl, cfg.cover === true ? [0, 0] : cfg.offset);
    }
    else {
      var ref$2 = cfg.anchorEl.getBoundingClientRect();
      var anchorTop = ref$2.top;
      var anchorLeft = ref$2.left;
      var top$1 = anchorTop + cfg.absoluteOffset.top,
        left$1 = anchorLeft + cfg.absoluteOffset.left;

      anchorProps = { top: top$1, left: left$1, width: 1, height: 1, right: left$1 + 1, center: top$1, middle: left$1, bottom: top$1 + 1 };
    }

    var elStyle = {
      maxHeight: cfg.maxHeight,
      maxWidth: cfg.maxWidth,
      visibility: 'visible'
    };

    if (cfg.fit === true || cfg.cover === true) {
      elStyle.minWidth = anchorProps.width + 'px';
      if (cfg.cover === true) {
        elStyle.minHeight = anchorProps.height + 'px';
      }
    }

    Object.assign(cfg.el.style, elStyle);

    var
      targetProps = getTargetProps(cfg.el),
      props = {
        top: anchorProps[cfg.anchorOrigin.vertical] - targetProps[cfg.selfOrigin.vertical],
        left: anchorProps[cfg.anchorOrigin.horizontal] - targetProps[cfg.selfOrigin.horizontal]
      };

    applyBoundaries(props, anchorProps, targetProps, cfg.anchorOrigin, cfg.selfOrigin);

    elStyle = {
      top: Math.floor(props.top) + 'px',
      left: Math.floor(props.left) + 'px'
    };

    if (props.maxHeight !== void 0) {
      elStyle.maxHeight = Math.floor(props.maxHeight) + 'px';

      if (anchorProps.height > props.maxHeight) {
        elStyle.minHeight = elStyle.maxHeight;
      }
    }
    if (props.maxWidth !== void 0) {
      elStyle.maxWidth = Math.floor(props.maxWidth) + 'px';

      if (anchorProps.width > props.maxWidth) {
        elStyle.minWidth = elStyle.maxWidth;
      }
    }

    Object.assign(cfg.el.style, elStyle);

    // restore scroll position
    if (cfg.el.scrollTop !== scrollTop) {
      cfg.el.scrollTop = scrollTop;
    }
    if (cfg.el.scrollLeft !== scrollLeft) {
      cfg.el.scrollLeft = scrollLeft;
    }
  }

  function applyBoundaries (props, anchorProps, targetProps, anchorOrigin, selfOrigin) {
    var
      currentHeight = targetProps.bottom,
      currentWidth = targetProps.right,
      margin = getScrollbarWidth(),
      innerHeight = window.innerHeight - margin,
      innerWidth = document.body.clientWidth;

    if (props.top < 0 || props.top + currentHeight > innerHeight) {
      if (selfOrigin.vertical === 'center') {
        props.top = anchorProps[anchorOrigin.vertical] > innerHeight / 2
          ? Math.max(0, innerHeight - currentHeight)
          : 0;
        props.maxHeight = Math.min(currentHeight, innerHeight);
      }
      else if (anchorProps[anchorOrigin.vertical] > innerHeight / 2) {
        var anchorY = Math.min(
          innerHeight,
          anchorOrigin.vertical === 'center'
            ? anchorProps.center
            : (anchorOrigin.vertical === selfOrigin.vertical ? anchorProps.bottom : anchorProps.top)
        );
        props.maxHeight = Math.min(currentHeight, anchorY);
        props.top = Math.max(0, anchorY - currentHeight);
      }
      else {
        props.top = Math.max(0, anchorOrigin.vertical === 'center'
          ? anchorProps.center
          : (anchorOrigin.vertical === selfOrigin.vertical ? anchorProps.top : anchorProps.bottom)
        );
        props.maxHeight = Math.min(currentHeight, innerHeight - props.top);
      }
    }

    if (props.left < 0 || props.left + currentWidth > innerWidth) {
      props.maxWidth = Math.min(currentWidth, innerWidth);
      if (selfOrigin.horizontal === 'middle') {
        props.left = anchorProps[anchorOrigin.horizontal] > innerWidth / 2
          ? Math.max(0, innerWidth - currentWidth)
          : 0;
      }
      else if (anchorProps[anchorOrigin.horizontal] > innerWidth / 2) {
        var anchorX = Math.min(
          innerWidth,
          anchorOrigin.horizontal === 'middle'
            ? anchorProps.middle
            : (anchorOrigin.horizontal === selfOrigin.horizontal ? anchorProps.right : anchorProps.left)
        );
        props.maxWidth = Math.min(currentWidth, anchorX);
        props.left = Math.max(0, anchorX - props.maxWidth);
      }
      else {
        props.left = Math.max(0, anchorOrigin.horizontal === 'middle'
          ? anchorProps.middle
          : (anchorOrigin.horizontal === selfOrigin.horizontal ? anchorProps.left : anchorProps.right)
        );
        props.maxWidth = Math.min(currentWidth, innerWidth - props.left);
      }
    }
  }

  var QMenu = Vue.extend({
    name: 'QMenu',

    mixins: [ DarkMixin, AnchorMixin, ModelToggleMixin, PortalMixin, TransitionMixin ],

    directives: {
      ClickOutside: ClickOutside
    },

    props: {
      persistent: Boolean,
      autoClose: Boolean,
      separateClosePopup: Boolean,

      noRefocus: Boolean,
      noFocus: Boolean,

      fit: Boolean,
      cover: Boolean,

      square: Boolean,

      anchor: {
        type: String,
        validator: validatePosition
      },
      self: {
        type: String,
        validator: validatePosition
      },
      offset: {
        type: Array,
        validator: validateOffset
      },

      scrollTarget: {
        default: void 0
      },

      touchPosition: Boolean,

      maxHeight: {
        type: String,
        default: null
      },
      maxWidth: {
        type: String,
        default: null
      }
    },

    computed: {
      horizSide: function horizSide () {
        return this.$q.lang.rtl === true ? 'right' : 'left'
      },

      anchorOrigin: function anchorOrigin () {
        return parsePosition(
          this.anchor || (
            this.cover === true ? "center middle" : ("bottom " + (this.horizSide))
          )
        )
      },

      selfOrigin: function selfOrigin () {
        return this.cover === true
          ? this.anchorOrigin
          : parsePosition(this.self || ("top " + (this.horizSide)))
      },

      menuClass: function menuClass () {
        return (this.square === true ? ' q-menu--square' : '') +
          (this.isDark === true ? ' q-menu--dark q-dark' : '')
      },

      hideOnRouteChange: function hideOnRouteChange () {
        return this.persistent !== true
      }
    },

    methods: {
      focus: function focus () {
        var node = this.__portal !== void 0 && this.__portal.$refs !== void 0
          ? this.__portal.$refs.inner
          : void 0;

        if (node !== void 0 && node.contains(document.activeElement) !== true) {
          node = node.querySelector('[autofocus], [data-autofocus]') || node;
          node.focus();
        }
      },

      __show: function __show (evt) {
        var this$1 = this;

        // IE can have null document.activeElement
        this.__refocusTarget = this.noRefocus === false && document.activeElement !== null
          ? document.activeElement
          : void 0;

        EscapeKey.register(this, function () {
          if (this$1.persistent !== true) {
            this$1.$emit('escape-key');
            this$1.hide();
          }
        });

        this.__showPortal();
        this.__configureScrollTarget();

        this.absoluteOffset = void 0;

        if (evt !== void 0 && (this.touchPosition || this.contextMenu)) {
          var pos = position(evt);

          if (pos.left !== void 0) {
            var ref = this.anchorEl.getBoundingClientRect();
            var top = ref.top;
            var left = ref.left;
            this.absoluteOffset = { left: pos.left - left, top: pos.top - top };
          }
        }

        if (this.unwatch === void 0) {
          this.unwatch = this.$watch(function () { return this$1.$q.screen.width + '|' + this$1.$q.screen.height; }, this.updatePosition);
        }

        this.$el.dispatchEvent(create('popup-show', { bubbles: true }));

        // IE can have null document.activeElement
        if (this.noFocus !== true && document.activeElement !== null) {
          document.activeElement.blur();
        }

        this.__nextTick(function () {
          this$1.updatePosition();
          this$1.noFocus !== true && this$1.focus();
        });

        this.__setTimeout(function () {
          // required in order to avoid the "double-tap needed" issue
          if (this$1.$q.platform.is.ios === true) {
            // if auto-close, then this click should
            // not close the menu
            this$1.__avoidAutoClose = this$1.autoClose;
            this$1.__portal.$el.click();
          }

          this$1.updatePosition();
          this$1.$emit('show', evt);
        }, 300);
      },

      __hide: function __hide (evt) {
        var this$1 = this;

        this.__anchorCleanup(true);

        // check null for IE
        if (
          this.__refocusTarget !== void 0 &&
          this.__refocusTarget !== null &&
          (
            // menu was hidden from code or ESC plugin
            evt === void 0 ||
            // menu was not closed from a mouse or touch clickOutside
            evt.qClickOutside !== true
          )
        ) {
          this.__refocusTarget.focus();
        }

        this.$el.dispatchEvent(create('popup-hide', { bubbles: true }));

        this.__setTimeout(function () {
          this$1.__hidePortal();
          this$1.$emit('hide', evt);
        }, 300);
      },

      __anchorCleanup: function __anchorCleanup (hiding) {
        this.absoluteOffset = void 0;

        if (this.unwatch !== void 0) {
          this.unwatch();
          this.unwatch = void 0;
        }

        if (hiding === true || this.showing === true) {
          EscapeKey.pop(this);
          this.__unconfigureScrollTarget();
        }
      },

      __unconfigureScrollTarget: function __unconfigureScrollTarget () {
        if (this.__scrollTarget !== void 0) {
          this.__changeScrollEvent(this.__scrollTarget);
          this.__scrollTarget = void 0;
        }
      },

      __configureScrollTarget: function __configureScrollTarget () {
        if (this.anchorEl !== void 0 || this.scrollTarget !== void 0) {
          this.__scrollTarget = getScrollTarget(this.anchorEl, this.scrollTarget);
          this.__changeScrollEvent(this.__scrollTarget, this.updatePosition);
        }
      },

      __onAutoClose: function __onAutoClose (e) {
        // if auto-close, then the ios double-tap fix which
        // issues a click should not close the menu
        if (this.__avoidAutoClose !== true) {
          closePortalMenus(this, e);
          this.$listeners.click !== void 0 && this.$emit('click', e);
        }
        else {
          this.__avoidAutoClose = false;
        }
      },

      updatePosition: function updatePosition () {
        if (this.anchorEl === void 0 || this.__portal === void 0) {
          return
        }

        var el = this.__portal.$el;

        if (el.nodeType === 8) { // IE replaces the comment with delay
          setTimeout(this.updatePosition, 25);
          return
        }

        setPosition({
          el: el,
          offset: this.offset,
          anchorEl: this.anchorEl,
          anchorOrigin: this.anchorOrigin,
          selfOrigin: this.selfOrigin,
          absoluteOffset: this.absoluteOffset,
          fit: this.fit,
          cover: this.cover,
          maxHeight: this.maxHeight,
          maxWidth: this.maxWidth
        });
      },

      __onClickOutside: function __onClickOutside (e) {
        if (this.persistent !== true && this.showing === true) {
          var targetClassList = e.target.classList;

          this.hide(e);
          if (
            // always prevent touch event
            e.type === 'touchstart' ||
            // prevent click if it's on a dialog backdrop
            targetClassList.contains('q-dialog__backdrop')
          ) {
            stopAndPrevent(e);
          }
          return true
        }
      },

      __renderPortal: function __renderPortal (h) {
        var on = Object.assign({}, this.$listeners,
          // stop propagating these events from children
          {input: stop,
          'popup-show': stop,
          'popup-hide': stop});

        if (this.autoClose === true) {
          on.click = this.__onAutoClose;
        }

        return h('transition', {
          props: { name: this.transition }
        }, [
          this.showing === true ? h('div', {
            ref: 'inner',
            staticClass: 'q-menu q-position-engine scroll' + this.menuClass,
            class: this.contentClass,
            style: this.contentStyle,
            attrs: Object.assign({}, {tabindex: -1},
              this.$attrs),
            on: on,
            directives: [{
              name: 'click-outside',
              value: this.__onClickOutside,
              arg: this.anchorEl
            }]
          }, slot(this, 'default')) : null
        ])
      }
    },

    mounted: function mounted () {
      this.__processModelChange(this.value);
    },

    beforeDestroy: function beforeDestroy () {
      // When the menu is destroyed while open we can only emit the event on anchorEl
      if (this.showing === true && this.anchorEl !== void 0) {
        this.anchorEl.dispatchEvent(
          create('popup-hide', { bubbles: true })
        );
      }
    }
  });

  var QBtnDropdown = Vue.extend({
    name: 'QBtnDropdown',

    mixins: [ BtnMixin ],

    props: {
      value: Boolean,
      split: Boolean,
      dropdownIcon: String,

      contentClass: [Array, String, Object],
      contentStyle: [Array, String, Object],

      cover: Boolean,
      persistent: Boolean,
      autoClose: Boolean,

      menuAnchor: {
        type: String,
        default: 'bottom right'
      },
      menuSelf: {
        type: String,
        default: 'top right'
      },
      menuOffset: Array,

      disableMainBtn: Boolean,
      disableDropdown: Boolean
    },

    data: function data () {
      return {
        showing: this.value
      }
    },

    watch: {
      value: function value (val) {
        this.$refs.menu !== void 0 && this.$refs.menu[val ? 'show' : 'hide']();
      }
    },

    render: function render (h) {
      var this$1 = this;

      var label = slot(this, 'label', []);
      var attrs = { 'aria-expanded': this.showing === true ? 'true' : 'false', 'aria-haspopup': true };

      var Arrow = [
        h(QIcon, {
          props: {
            name: this.dropdownIcon || this.$q.iconSet.arrow.dropdown
          },
          staticClass: 'q-btn-dropdown__arrow',
          class: {
            'rotate-180': this.showing,
            'q-btn-dropdown__arrow-container': this.split === false
          }
        })
      ];

      this.disableDropdown !== true && Arrow.push(
        h(QMenu, {
          ref: 'menu',
          props: {
            cover: this.cover,
            fit: true,
            persistent: this.persistent,
            autoClose: this.autoClose,
            anchor: this.menuAnchor,
            self: this.menuSelf,
            offset: this.menuOffset,
            contentClass: this.contentClass,
            contentStyle: this.contentStyle,
            separateClosePopup: true
          },
          on: cache(this, 'menu', {
            'before-show': function (e) {
              this$1.showing = true;
              this$1.$emit('before-show', e);
            },
            show: function (e) {
              this$1.$emit('show', e);
              this$1.$emit('input', true);
            },
            'before-hide': function (e) {
              this$1.showing = false;
              this$1.$emit('before-hide', e);
            },
            hide: function (e) {
              this$1.$emit('hide', e);
              this$1.$emit('input', false);
            }
          })
        }, slot(this, 'default'))
      );

      if (this.split === false) {
        return h(QBtn, {
          class: 'q-btn-dropdown q-btn-dropdown--simple',
          props: Object.assign({}, this.$props,
            {disable: this.disable === true || this.disableMainBtn === true,
            noWrap: true,
            round: false}),
          attrs: attrs,
          on: cache(this, 'nonSpl', {
            click: function (e) {
              this$1.$emit('click', e);
            }
          })
        }, label.concat(Arrow))
      }

      var Btn = h(QBtn, {
        class: 'q-btn-dropdown--current',
        props: Object.assign({}, this.$props,
          {disable: this.disable === true || this.disableMainBtn === true,
          noWrap: true,
          iconRight: this.iconRight,
          round: false}),
        on: cache(this, 'spl', {
          click: function (e) {
            this$1.hide();
            this$1.$emit('click', e);
          }
        })
      }, label);

      return h(QBtnGroup, {
        props: {
          outline: this.outline,
          flat: this.flat,
          rounded: this.rounded,
          push: this.push,
          unelevated: this.unelevated,
          glossy: this.glossy,
          stretch: this.stretch
        },
        staticClass: 'q-btn-dropdown q-btn-dropdown--split no-wrap q-btn-item'
      }, [
        Btn,

        h(QBtn, {
          staticClass: 'q-btn-dropdown__arrow-container',
          attrs: attrs,
          props: {
            disable: this.disable === true || this.disableDropdown === true,
            outline: this.outline,
            flat: this.flat,
            rounded: this.rounded,
            push: this.push,
            size: this.size,
            color: this.color,
            textColor: this.textColor,
            dense: this.dense,
            ripple: this.ripple
          }
        }, Arrow)
      ])
    },

    methods: {
      toggle: function toggle (evt) {
        this.$refs.menu && this.$refs.menu.toggle(evt);
      },

      show: function show (evt) {
        this.$refs.menu && this.$refs.menu.show(evt);
      },

      hide: function hide (evt) {
        this.$refs.menu && this.$refs.menu.hide(evt);
      }
    },

    mounted: function mounted () {
      this.value === true && this.show();
    }
  });

  var FormMixin = {
    props: {
      name: String
    },

    computed: {
      formAttrs: function formAttrs () {
        return {
          type: 'hidden',
          name: this.name,
          value: this.value
        }
      }
    },

    methods: {
      __injectFormInput: function __injectFormInput (child, action, className) {
        child[action](
          this.$createElement('input', {
            staticClass: 'hidden',
            class: className,
            attrs: this.formAttrs,
            domProps: this.formDomProps
          })
        );
      }
    }
  };

  var FormFieldMixin = {
    props: {
      name: String
    },

    computed: {
      nameProp: function nameProp () {
        return this.name || this.for
      }
    }
  };

  var QBtnToggle = Vue.extend({
    name: 'QBtnToggle',

    mixins: [ RippleMixin, FormMixin ],

    props: {
      value: {
        required: true
      },

      options: {
        type: Array,
        required: true,
        validator: function (v) { return v.every(
          function (opt) { return ('label' in opt || 'icon' in opt || 'slot' in opt) && 'value' in opt; }
        ); }
      },

      // To avoid seeing the active raise shadow through the transparent button, give it a color (even white).
      color: String,
      textColor: String,
      toggleColor: {
        type: String,
        default: 'primary'
      },
      toggleTextColor: String,

      outline: Boolean,
      flat: Boolean,
      unelevated: Boolean,
      rounded: Boolean,
      push: Boolean,
      glossy: Boolean,

      size: String,

      noCaps: Boolean,
      noWrap: Boolean,
      dense: Boolean,
      readonly: Boolean,
      disable: Boolean,

      stack: Boolean,
      stretch: Boolean,

      spread: Boolean,

      clearable: Boolean
    },

    computed: {
      hasActiveValue: function hasActiveValue () {
        var this$1 = this;

        return this.options.find(function (opt) { return opt.value === this$1.value; }) !== void 0
      },

      formAttrs: function formAttrs () {
        return {
          type: 'hidden',
          name: this.name,
          value: this.value
        }
      }
    },

    methods: {
      __set: function __set (value, opt) {
        if (this.readonly !== true) {
          if (this.value === value) {
            if (this.clearable === true) {
              this.$emit('input', null, null);
              this.$emit('clear');
            }
          }
          else {
            this.$emit('input', value, opt);
          }
        }
      }
    },

    render: function render (h) {
      var this$1 = this;

      var child = this.options.map(function (opt, i) {
        return h(QBtn, {
          key: i,
          on: { click: function () { return this$1.__set(opt.value, opt); } },
          props: {
            disable: this$1.disable || opt.disable,
            label: opt.label,
            // Colors come from the button specific options first, then from general props
            color: opt.value === this$1.value ? opt.toggleColor || this$1.toggleColor : opt.color || this$1.color,
            textColor: opt.value === this$1.value ? opt.toggleTextColor || this$1.toggleTextColor : opt.textColor || this$1.textColor,
            icon: opt.icon,
            iconRight: opt.iconRight,
            noCaps: this$1.noCaps === true || opt.noCaps === true,
            noWrap: this$1.noWrap === true || opt.noWrap === true,
            outline: this$1.outline,
            flat: this$1.flat,
            rounded: this$1.rounded,
            push: this$1.push,
            unelevated: this$1.unelevated,
            size: this$1.size,
            dense: this$1.dense,
            ripple: this$1.ripple !== void 0 ? this$1.ripple : opt.ripple,
            stack: this$1.stack === true || opt.stack === true,
            tabindex: opt.tabindex,
            stretch: this$1.stretch
          }
        }, opt.slot !== void 0 ? slot(this$1, opt.slot) : void 0)
      });

      if (this.name !== void 0 && this.disable !== true && this.hasActiveValue === true) {
        this.__injectFormInput(child, 'push');
      }

      return h(QBtnGroup, {
        staticClass: 'q-btn-toggle',
        props: {
          outline: this.outline,
          flat: this.flat,
          rounded: this.rounded,
          push: this.push,
          stretch: this.stretch,
          unelevated: this.unelevated,
          glossy: this.glossy,
          spread: this.spread
        },
        on: this.$listeners
      }, child)
    }
  });

  var QCard = Vue.extend({
    name: 'QCard',

    mixins: [ DarkMixin, TagMixin ],

    props: {
      square: Boolean,
      flat: Boolean,
      bordered: Boolean
    },

    computed: {
      classes: function classes () {
        return 'q-card' +
          (this.isDark === true ? ' q-card--dark q-dark' : '') +
          (this.bordered === true ? ' q-card--bordered' : '') +
          (this.square === true ? ' q-card--square no-border-radius' : '') +
          (this.flat === true ? ' q-card--flat no-shadow' : '')
      }
    },

    render: function render (h) {
      return h(this.tag, {
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QCardSection = Vue.extend({
    name: 'QCardSection',

    mixins: [ TagMixin ],

    props: {
      horizontal: Boolean
    },

    computed: {
      classes: function classes () {
        return 'q-card__section ' +
          "q-card__section--" + (this.horizontal === true ? 'horiz row no-wrap' : 'vert')
      }
    },

    render: function render (h) {
      return h(this.tag, {
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QCardActions = Vue.extend({
    name: 'QCardActions',

    mixins: [ AlignMixin ],

    props: {
      vertical: Boolean
    },

    computed: {
      classes: function classes () {
        return ("q-card__actions--" + (this.vertical === true ? 'vert column' : 'horiz row') + " " + (this.alignClass))
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-card__actions',
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  function parseArg (arg) {
    // delta (min velocity -- dist / time)
    // mobile min distance on first move
    // desktop min distance until deciding if it's a swipe or not
    var data = [0.06, 6, 50];

    if (typeof arg === 'string' && arg.length) {
      arg.split(':').forEach(function (val, index) {
        var v = parseFloat(val);
        v && (data[index] = v);
      });
    }

    return data
  }

  var TouchSwipe = {
    name: 'touch-swipe',

    bind: function bind (el, ref) {
      var value = ref.value;
      var arg = ref.arg;
      var modifiers = ref.modifiers;

      // early return, we don't need to do anything
      if (modifiers.mouse !== true && client.has.touch !== true) {
        return
      }

      var mouseCapture = modifiers.mouseCapture === true ? 'Capture' : '';

      var ctx = {
        handler: value,
        sensitivity: parseArg(arg),

        modifiers: modifiers,
        direction: getModifierDirections(modifiers),

        noop: noop,

        mouseStart: function mouseStart (evt) {
          if (shouldStart(evt, ctx) && leftClick(evt)) {
            addEvt(ctx, 'temp', [
              [ document, 'mousemove', 'move', ("notPassive" + mouseCapture) ],
              [ document, 'mouseup', 'end', 'notPassiveCapture' ]
            ]);
            ctx.start(evt, true);
          }
        },

        touchStart: function touchStart (evt) {
          if (shouldStart(evt, ctx)) {
            var target = getTouchTarget(evt.target);
            addEvt(ctx, 'temp', [
              [ target, 'touchmove', 'move', 'notPassiveCapture' ],
              [ target, 'touchcancel', 'end', 'notPassiveCapture' ],
              [ target, 'touchend', 'end', 'notPassiveCapture' ]
            ]);
            ctx.start(evt);
          }
        },

        start: function start (evt, mouseEvent) {
          client.is.firefox === true && preventDraggable(el, true);

          var pos = position(evt);

          ctx.event = {
            x: pos.left,
            y: pos.top,
            time: Date.now(),
            mouse: mouseEvent === true,
            dir: false
          };
        },

        move: function move (evt) {
          if (ctx.event === void 0) {
            return
          }

          if (ctx.event.dir !== false) {
            stopAndPrevent(evt);
            return
          }

          var time = Date.now() - ctx.event.time;

          if (time === 0) {
            return
          }

          var
            pos = position(evt),
            distX = pos.left - ctx.event.x,
            absX = Math.abs(distX),
            distY = pos.top - ctx.event.y,
            absY = Math.abs(distY);

          if (ctx.event.mouse !== true) {
            if (absX < ctx.sensitivity[1] && absY < ctx.sensitivity[1]) {
              ctx.end(evt);
              return
            }
          }
          else if (absX < ctx.sensitivity[2] && absY < ctx.sensitivity[2]) {
            return
          }

          var
            velX = absX / time,
            velY = absY / time;

          if (
            ctx.direction.vertical === true &&
            absX < absY &&
            absX < 100 &&
            velY > ctx.sensitivity[0]
          ) {
            ctx.event.dir = distY < 0 ? 'up' : 'down';
          }

          if (
            ctx.direction.horizontal === true &&
            absX > absY &&
            absY < 100 &&
            velX > ctx.sensitivity[0]
          ) {
            ctx.event.dir = distX < 0 ? 'left' : 'right';
          }

          if (
            ctx.direction.up === true &&
            absX < absY &&
            distY < 0 &&
            absX < 100 &&
            velY > ctx.sensitivity[0]
          ) {
            ctx.event.dir = 'up';
          }

          if (
            ctx.direction.down === true &&
            absX < absY &&
            distY > 0 &&
            absX < 100 &&
            velY > ctx.sensitivity[0]
          ) {
            ctx.event.dir = 'down';
          }

          if (
            ctx.direction.left === true &&
            absX > absY &&
            distX < 0 &&
            absY < 100 &&
            velX > ctx.sensitivity[0]
          ) {
            ctx.event.dir = 'left';
          }

          if (
            ctx.direction.right === true &&
            absX > absY &&
            distX > 0 &&
            absY < 100 &&
            velX > ctx.sensitivity[0]
          ) {
            ctx.event.dir = 'right';
          }

          if (ctx.event.dir !== false) {
            stopAndPrevent(evt);

            if (ctx.event.mouse === true) {
              document.body.classList.add('no-pointer-events');
              document.body.classList.add('non-selectable');
              clearSelection();

              ctx.styleCleanup = function (withDelay) {
                ctx.styleCleanup = void 0;

                document.body.classList.remove('non-selectable');

                var remove = function () {
                  document.body.classList.remove('no-pointer-events');
                };

                if (withDelay === true) { setTimeout(remove, 50); }
                else { remove(); }
              };
            }

            ctx.handler({
              evt: evt,
              touch: ctx.event.mouse !== true,
              mouse: ctx.event.mouse,
              direction: ctx.event.dir,
              duration: time,
              distance: {
                x: absX,
                y: absY
              }
            });
          }
          else {
            ctx.end(evt);
          }
        },

        end: function end (evt) {
          if (ctx.event === void 0) {
            return
          }

          cleanEvt(ctx, 'temp');
          client.is.firefox === true && preventDraggable(el, false);
          ctx.styleCleanup !== void 0 && ctx.styleCleanup(true);
          evt !== void 0 && ctx.event.dir !== false && stopAndPrevent(evt);

          ctx.event = void 0;
        }
      };

      if (el.__qtouchswipe) {
        el.__qtouchswipe_old = el.__qtouchswipe;
      }

      el.__qtouchswipe = ctx;

      modifiers.mouse === true && addEvt(ctx, 'main', [
        [ el, 'mousedown', 'mouseStart', ("passive" + mouseCapture) ]
      ]);

      client.has.touch === true && addEvt(ctx, 'main', [
        [ el, 'touchstart', 'touchStart', ("passive" + (modifiers.capture === true ? 'Capture' : '')) ],
        [ el, 'touchmove', 'noop', "notPassiveCapture" ]
      ]);
    },

    update: function update (el, binding) {
      el.__qtouchswipe !== void 0 && updateModifiers(el.__qtouchswipe, binding);
    },

    unbind: function unbind (el) {
      var ctx = el.__qtouchswipe_old || el.__qtouchswipe;

      if (ctx !== void 0) {
        cleanEvt(ctx, 'main');
        cleanEvt(ctx, 'temp');

        client.is.firefox === true && preventDraggable(el, false);
        ctx.styleCleanup !== void 0 && ctx.styleCleanup();

        delete el[el.__qtouchswipe_old ? '__qtouchswipe_old' : '__qtouchswipe'];
      }
    }
  };

  var PanelWrapper = Vue.extend({
    name: 'QTabPanelWrapper',

    render: function render (h) {
      return h('div', {
        staticClass: 'q-panel scroll',
        attrs: { role: 'tabpanel' },
        // stop propagation of content emitted @input
        // which would tamper with Panel's model
        on: cache(this, 'stop', { input: stop })
      }, slot(this, 'default'))
    }
  });

  var PanelParentMixin = {
    directives: {
      TouchSwipe: TouchSwipe
    },

    props: {
      value: {
        required: true
      },

      animated: Boolean,
      infinite: Boolean,
      swipeable: Boolean,
      vertical: Boolean,

      transitionPrev: String,
      transitionNext: String,

      keepAlive: Boolean
    },

    data: function data () {
      return {
        panelIndex: null,
        panelTransition: null
      }
    },

    computed: {
      panelDirectives: function panelDirectives () {
        if (this.swipeable === true) {
          return [{
            name: 'touch-swipe',
            value: this.__swipe,
            modifiers: {
              horizontal: this.vertical !== true,
              vertical: this.vertical,
              mouse: true
            }
          }]
        }
      },

      contentKey: function contentKey () {
        return typeof this.value === 'string' || typeof this.value === 'number'
          ? this.value
          : String(this.value)
      },

      transitionPrevComputed: function transitionPrevComputed () {
        return this.transitionPrev || ("slide-" + (this.vertical === true ? 'down' : 'right'))
      },

      transitionNextComputed: function transitionNextComputed () {
        return this.transitionNext || ("slide-" + (this.vertical === true ? 'up' : 'left'))
      }
    },

    watch: {
      value: function value (newVal, oldVal) {
        var this$1 = this;

        var index = this.__isValidPanelName(newVal) === true
          ? this.__getPanelIndex(newVal)
          : -1;

        if (this.__forcedPanelTransition !== true) {
          this.__updatePanelTransition(
            index === -1 ? 0 : (index < this.__getPanelIndex(oldVal) ? -1 : 1)
          );
        }

        if (this.panelIndex !== index) {
          this.panelIndex = index;
          this.$emit('before-transition', newVal, oldVal);
          this.$nextTick(function () {
            this$1.$emit('transition', newVal, oldVal);
          });
        }
      }
    },

    methods: {
      next: function next () {
        this.__go(1);
      },

      previous: function previous () {
        this.__go(-1);
      },

      goTo: function goTo (name) {
        this.$emit('input', name);
      },

      __isValidPanelName: function __isValidPanelName (name) {
        return name !== void 0 && name !== null && name !== ''
      },

      __getPanelIndex: function __getPanelIndex (name) {
        return this.panels.findIndex(function (panel) {
          var opt = panel.componentOptions;
          return opt &&
            opt.propsData.name === name &&
            opt.propsData.disable !== '' &&
            opt.propsData.disable !== true
        })
      },

      __getAllPanels: function __getAllPanels () {
        var this$1 = this;

        return this.panels.filter(
          function (panel) { return panel.componentOptions !== void 0 &&
            this$1.__isValidPanelName(panel.componentOptions.propsData.name); }
        )
      },

      __getAvailablePanels: function __getAvailablePanels () {
        return this.panels.filter(function (panel) {
          var opt = panel.componentOptions;
          return opt &&
            opt.propsData.name !== void 0 &&
            opt.propsData.disable !== '' &&
            opt.propsData.disable !== true
        })
      },

      __updatePanelTransition: function __updatePanelTransition (direction) {
        var val = direction !== 0 && this.animated === true && this.panelIndex !== -1
          ? 'q-transition--' + (direction === -1 ? this.transitionPrevComputed : this.transitionNextComputed)
          : null;

        if (this.panelTransition !== val) {
          this.panelTransition = val;
        }
      },

      __go: function __go (direction, startIndex) {
        var this$1 = this;
        if ( startIndex === void 0 ) startIndex = this.panelIndex;

        var index = startIndex + direction;
        var slots = this.panels;

        while (index > -1 && index < slots.length) {
          var opt = slots[index].componentOptions;

          if (
            opt !== void 0 &&
            opt.propsData.disable !== '' &&
            opt.propsData.disable !== true
          ) {
            this.__updatePanelTransition(direction);
            this.__forcedPanelTransition = true;
            this.$emit('input', slots[index].componentOptions.propsData.name);
            setTimeout(function () {
              this$1.__forcedPanelTransition = false;
            });
            return
          }

          index += direction;
        }

        if (this.infinite === true && slots.length > 0 && startIndex !== -1 && startIndex !== slots.length) {
          this.__go(direction, direction === -1 ? slots.length : -1);
        }
      },

      __swipe: function __swipe (evt) {
        var dir = this.vertical === true ? 'up' : 'left';
        this.__go((this.$q.lang.rtl === true ? -1 : 1) * (evt.direction === dir ? 1 : -1));
      },

      __updatePanelIndex: function __updatePanelIndex () {
        var index = this.__getPanelIndex(this.value);

        if (this.panelIndex !== index) {
          this.panelIndex = index;
        }

        return true
      },

      __getPanelContent: function __getPanelContent (h) {
        if (this.panels.length === 0) {
          return
        }

        var panel = this.__isValidPanelName(this.value) &&
          this.__updatePanelIndex() &&
          this.panels[this.panelIndex];

        var content = this.keepAlive === true
          ? [
            h('keep-alive', [
              h(PanelWrapper, {
                key: this.contentKey
              }, [ panel ])
            ])
          ]
          : [
            h('div', {
              staticClass: 'q-panel scroll',
              key: this.contentKey,
              attrs: { role: 'tabpanel' },
              // stop propagation of content emitted @input
              // which would tamper with Panel's model
              on: cache(this, 'stop', { input: stop })
            }, [ panel ])
          ];

        return this.animated === true
          ? [
            h('transition', {
              props: {
                name: this.panelTransition
              }
            }, content)
          ]
          : content
      }
    },

    render: function render (h) {
      this.panels = slot(this, 'default', []);
      return this.__renderPanels(h)
    }
  };

  var PanelChildMixin = {
    props: {
      name: {
        required: true
      },
      disable: Boolean
    }
  };

  var FullscreenMixin = {
    props: {
      fullscreen: Boolean,
      noRouteFullscreenExit: Boolean
    },

    data: function data () {
      return {
        inFullscreen: false
      }
    },

    watch: {
      $route: function $route () {
        this.noRouteFullscreenExit !== true && this.exitFullscreen();
      },

      fullscreen: function fullscreen (v) {
        if (this.inFullscreen !== v) {
          this.toggleFullscreen();
        }
      },

      inFullscreen: function inFullscreen (v) {
        this.$emit('update:fullscreen', v);
        this.$emit('fullscreen', v);
      }
    },

    methods: {
      toggleFullscreen: function toggleFullscreen () {
        if (this.inFullscreen === true) {
          this.exitFullscreen();
        }
        else {
          this.setFullscreen();
        }
      },

      setFullscreen: function setFullscreen () {
        if (this.inFullscreen === true) {
          return
        }

        this.inFullscreen = true;
        this.container = this.$el.parentNode;
        this.container.replaceChild(this.fullscreenFillerNode, this.$el);
        document.body.appendChild(this.$el);
        document.body.classList.add('q-body--fullscreen-mixin');

        this.__historyFullscreen = {
          handler: this.exitFullscreen
        };
        History.add(this.__historyFullscreen);
      },

      exitFullscreen: function exitFullscreen () {
        var this$1 = this;

        if (this.inFullscreen !== true) {
          return
        }

        if (this.__historyFullscreen !== void 0) {
          History.remove(this.__historyFullscreen);
          this.__historyFullscreen = void 0;
        }
        this.container.replaceChild(this.$el, this.fullscreenFillerNode);
        document.body.classList.remove('q-body--fullscreen-mixin');
        this.inFullscreen = false;

        if (this.$el.scrollIntoView !== void 0) {
          setTimeout(function () { this$1.$el.scrollIntoView(); });
        }
      }
    },

    beforeMount: function beforeMount () {
      this.fullscreenFillerNode = document.createElement('span');
    },

    mounted: function mounted () {
      this.fullscreen === true && this.setFullscreen();
    },

    beforeDestroy: function beforeDestroy () {
      this.exitFullscreen();
    }
  };

  var
    hasMap = typeof Map === 'function',
    hasSet = typeof Set === 'function',
    hasArrayBuffer = typeof ArrayBuffer === 'function';

  function isDeepEqual (a, b) {
    if (a === b) {
      return true
    }

    if (a !== null && b !== null && typeof a === 'object' && typeof b === 'object') {
      if (a.constructor !== b.constructor) {
        return false
      }

      var length, i, keys;

      if (a.constructor === Array) {
        length = a.length;

        if (length !== b.length) {
          return false
        }

        for (i = length; i-- !== 0;) {
          if (isDeepEqual(a[i], b[i]) !== true) {
            return false
          }
        }

        return true
      }

      if (hasMap === true && a.constructor === Map) {
        if (a.size !== b.size) {
          return false
        }

        i = a.entries().next();
        while (i.done !== true) {
          if (b.has(i.value[0]) !== true) {
            return false
          }
          i = i.next();
        }

        i = a.entries().next();
        while (i.done !== true) {
          if (isDeepEqual(i.value[1], b.get(i.value[0])) !== true) {
            return false
          }
          i = i.next();
        }

        return true
      }

      if (hasSet === true && a.constructor === Set) {
        if (a.size !== b.size) {
          return false
        }

        i = a.entries().next();
        while (i.done !== true) {
          if (b.has(i.value[0]) !== true) {
            return false
          }
          i = i.next();
        }

        return true
      }

      if (hasArrayBuffer === true && a.buffer != null && a.buffer.constructor === ArrayBuffer) {
        length = a.length;

        if (length !== b.length) {
          return false
        }

        for (i = length; i-- !== 0;) {
          if (a[i] !== b[i]) {
            return false
          }
        }

        return true
      }

      if (a.constructor === RegExp) {
        return a.source === b.source && a.flags === b.flags
      }

      if (a.valueOf !== Object.prototype.valueOf) {
        return a.valueOf() === b.valueOf()
      }

      if (a.toString !== Object.prototype.toString) {
        return a.toString() === b.toString()
      }

      keys = Object.keys(a);
      length = keys.length;

      if (length !== Object.keys(b).length) {
        return false
      }

      for (i = length; i-- !== 0;) {
        var key = keys[i];
        if (isDeepEqual(a[key], b[key]) !== true) {
          return false
        }
      }

      return true
    }

    // true if both NaN, false otherwise
    return a !== a && b !== b // eslint-disable-line no-self-compare
  }

  function isDate (v) {
    return Object.prototype.toString.call(v) === '[object Date]'
  }

  function isNumber (v) {
    return typeof v === 'number' && isFinite(v)
  }

  var QCarousel = Vue.extend({
    name: 'QCarousel',

    mixins: [ DarkMixin, PanelParentMixin, FullscreenMixin ],

    props: {
      height: String,
      padding: Boolean,

      controlType: {
        type: String,
        validator: function (v) { return [ 'regular', 'flat', 'outline', 'push', 'unelevated' ].includes(v); },
        default: 'flat'
      },
      controlColor: String,
      controlTextColor: String,

      autoplay: [Number, Boolean],

      arrows: Boolean,
      prevIcon: String,
      nextIcon: String,

      navigation: Boolean,
      navigationPosition: {
        type: String,
        validator: function (v) { return ['top', 'right', 'bottom', 'left'].includes(v); }
      },
      navigationIcon: String,

      thumbnails: Boolean
    },

    computed: {
      style: function style () {
        if (this.inFullscreen !== true && this.height !== void 0) {
          return {
            height: this.height
          }
        }
      },

      direction: function direction () {
        return this.vertical === true ? 'vertical' : 'horizontal'
      },

      classes: function classes () {
        return "q-carousel q-panel-parent q-carousel--with" + (this.padding === true ? '' : 'out') + "-padding" +
          (this.inFullscreen === true ? ' fullscreen' : '') +
          (this.isDark === true ? ' q-carousel--dark q-dark' : '') +
          (this.arrows === true ? (" q-carousel--arrows-" + (this.direction)) : '') +
          (this.navigation === true ? (" q-carousel--navigation-" + (this.navigationPositionComputed)) : '')
      },

      arrowIcons: function arrowIcons () {
        var ico = [
          this.prevIcon || this.$q.iconSet.carousel[this.vertical === true ? 'up' : 'left'],
          this.nextIcon || this.$q.iconSet.carousel[this.vertical === true ? 'down' : 'right']
        ];

        return this.vertical === false && this.$q.lang.rtl === true
          ? ico.reverse()
          : ico
      },

      navIcon: function navIcon () {
        return this.navigationIcon || this.$q.iconSet.carousel.navigationIcon
      },

      navigationPositionComputed: function navigationPositionComputed () {
        return this.navigationPosition || (this.vertical === true ? 'right' : 'bottom')
      },

      controlProps: function controlProps () {
        var obj;

        return ( obj = {
          color: this.controlColor,
          textColor: this.controlTextColor,
          round: true
        }, obj[this.controlType] = true, obj.dense = true, obj )
      },

      transitionPrevComputed: function transitionPrevComputed () {
        return this.transitionPrev || "fade"
      },

      transitionNextComputed: function transitionNextComputed () {
        return this.transitionNext || "fade"
      }
    },

    watch: {
      value: function value () {
        if (this.autoplay) {
          clearInterval(this.timer);
          this.__startTimer();
        }
      },

      autoplay: function autoplay (val) {
        if (val) {
          this.__startTimer();
        }
        else {
          clearInterval(this.timer);
        }
      }
    },

    methods: {
      __startTimer: function __startTimer () {
        this.timer = setTimeout(
          this.next,
          isNumber(this.autoplay) ? this.autoplay : 5000
        );
      },

      __getNavigationContainer: function __getNavigationContainer (h, type, mapping) {
        return h('div', {
          class: 'q-carousel__control q-carousel__navigation no-wrap absolute flex' +
            " q-carousel__navigation--" + type + " q-carousel__navigation--" + (this.navigationPositionComputed) +
            (this.controlColor !== void 0 ? (" text-" + (this.controlColor)) : '')
        }, [
          h('div', {
            staticClass: 'q-carousel__navigation-inner flex no-wrap justify-center'
          }, this.__getAvailablePanels().map(mapping))
        ])
      },

      __getContent: function __getContent (h) {
        var this$1 = this;

        var node = [];

        if (this.navigation === true) {
          node.push(this.__getNavigationContainer(h, 'buttons', function (panel) {
            var name = panel.componentOptions.propsData.name;

            return h(QBtn, {
              key: name,
              class: ("q-carousel__navigation-icon q-carousel__navigation-icon--" + (name === this$1.value ? '' : 'in') + "active"),
              props: Object.assign({
                icon: this$1.navIcon,
                size: 'sm'
              }, this$1.controlProps),
              on: cache(this$1, 'nav#' + name, { click: function () { this$1.goTo(name); } })
            })
          }));
        }
        else if (this.thumbnails === true) {
          var color = this.controlColor !== void 0
            ? (" text-" + (this.controlColor))
            : '';

          node.push(this.__getNavigationContainer(h, 'thumbnails', function (panel) {
            var slide = panel.componentOptions.propsData;

            return h('img', {
              class: "q-carousel__thumbnail q-carousel__thumbnail--" + (slide.name === this$1.value ? '' : 'in') + "active" + color,
              attrs: {
                src: slide.imgSrc
              },
              key: 'tmb#' + slide.name,
              on: cache(this$1, 'tmb#' + slide.name, { click: function () { this$1.goTo(slide.name); } })
            })
          }));
        }

        if (this.arrows === true) {
          node.push(
            h('div', {
              staticClass: ("q-carousel__control q-carousel__arrow q-carousel__prev-arrow q-carousel__prev-arrow--" + (this.direction) + " absolute flex flex-center")
            }, [
              h(QBtn, {
                props: Object.assign({ icon: this.arrowIcons[0] }, this.controlProps),
                on: cache(this, 'prev', { click: this.previous })
              })
            ]),
            h('div', {
              staticClass: ("q-carousel__control q-carousel__arrow q-carousel__next-arrow q-carousel__next-arrow--" + (this.direction) + " absolute flex flex-center")
            }, [
              h(QBtn, {
                props: Object.assign({ icon: this.arrowIcons[1] }, this.controlProps),
                on: cache(this, 'next', { click: this.next })
              })
            ])
          );
        }

        return mergeSlot(node, this, 'control')
      },

      __renderPanels: function __renderPanels (h) {
        return h('div', {
          style: this.style,
          class: this.classes,
          on: this.$listeners
        }, [
          h('div', {
            staticClass: 'q-carousel__slides-container',
            directives: this.panelDirectives
          }, this.__getPanelContent(h))
        ].concat(this.__getContent(h)))
      }
    },

    mounted: function mounted () {
      this.autoplay && this.__startTimer();
    },

    beforeDestroy: function beforeDestroy () {
      clearInterval(this.timer);
    }
  });

  var QCarouselSlide = Vue.extend({
    name: 'QCarouselSlide',

    mixins: [ PanelChildMixin ],

    props: {
      imgSrc: String
    },

    computed: {
      style: function style () {
        if (this.imgSrc) {
          return {
            backgroundImage: ("url(" + (this.imgSrc) + ")")
          }
        }
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-carousel__slide',
        style: this.style,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QCarouselControl = Vue.extend({
    name: 'QCarouselControl',

    props: {
      position: {
        type: String,
        default: 'bottom-right',
        validator: function (v) { return [
          'top-right', 'top-left',
          'bottom-right', 'bottom-left',
          'top', 'right', 'bottom', 'left'
        ].includes(v); }
      },
      offset: {
        type: Array,
        default: function () { return [18, 18]; },
        validator: function (v) { return v.length === 2; }
      }
    },

    computed: {
      classes: function classes () {
        return ("absolute-" + (this.position))
      },

      style: function style () {
        return {
          margin: ((this.offset[1]) + "px " + (this.offset[0]) + "px")
        }
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-carousel__control absolute',
        style: this.style,
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QChatMessage = Vue.extend({
    name: 'QChatMessage',

    props: {
      sent: Boolean,
      label: String,
      bgColor: String,
      textColor: String,
      name: String,
      avatar: String,
      text: Array,
      stamp: String,
      size: String,
      labelSanitize: Boolean,
      nameSanitize: Boolean,
      textSanitize: Boolean,
      stampSanitize: Boolean
    },

    computed: {
      textClass: function textClass () {
        return "q-message-text-content q-message-text-content--" + (this.op) +
          (this.textColor !== void 0 ? (" text-" + (this.textColor)) : '')
      },

      messageClass: function messageClass () {
        return "q-message-text q-message-text--" + (this.op) +
          (this.bgColor !== void 0 ? (" text-" + (this.bgColor)) : '')
      },

      containerClass: function containerClass () {
        return "q-message-container row items-end no-wrap" +
          (this.sent === true ? ' reverse' : '')
      },

      sizeClass: function sizeClass () {
        if (this.size !== void 0) {
          return ("col-" + (this.size))
        }
      },

      op: function op () {
        return this.sent === true ? 'sent' : 'received'
      }
    },

    methods: {
      __getText: function __getText (h) {
        var this$1 = this;

        var
          domPropText = this.textSanitize === true ? 'textContent' : 'innerHTML',
          domPropStamp = this.stampSanitize === true ? 'textContent' : 'innerHTML';

        return this.text.map(function (msg, index) {
          var obj, obj$1;

          return h('div', {
          key: index,
          class: this$1.messageClass
        }, [
          h('div', { class: this$1.textClass }, [
            h('div', { domProps: ( obj = {}, obj[domPropText] = msg, obj ) }),
            this$1.stamp
              ? h('div', {
                staticClass: 'q-message-stamp',
                domProps: ( obj$1 = {}, obj$1[domPropStamp] = this$1.stamp, obj$1 )
              })
              : null
          ])
        ]);
        })
      },

      __getMessage: function __getMessage (h) {
        var obj;

        var content = uniqueSlot(this, 'default', []);

        this.stamp !== void 0 && content.push(
          h('div', {
            staticClass: 'q-message-stamp',
            domProps: ( obj = {}, obj[this.stampSanitize === true ? 'textContent' : 'innerHTML'] = this.stamp, obj )
          })
        );

        return h('div', { class: this.messageClass }, [
          h('div', {
            staticClass: 'q-message-text-content',
            class: this.textClass
          }, content)
        ])
      }
    },

    render: function render (h) {
      var obj, obj$1;

      var container = [];

      if (this.$scopedSlots.avatar !== void 0) {
        container.push(this.$scopedSlots.avatar());
      }
      else if (this.avatar !== void 0) {
        container.push(
          h('img', {
            class: ("q-message-avatar q-message-avatar--" + (this.op)),
            attrs: { src: this.avatar, 'aria-hidden': 'true' }
          })
        );
      }

      var msg = [];

      this.name !== void 0 && msg.push(
        h('div', {
          class: ("q-message-name q-message-name--" + (this.op)),
          domProps: ( obj = {}, obj[this.nameSanitize === true ? 'textContent' : 'innerHTML'] = this.name, obj )
        })
      );

      this.text !== void 0 && msg.push(
        this.__getText(h)
      );

      this.$scopedSlots.default !== void 0 && msg.push(
        this.__getMessage(h)
      );

      container.push(
        h('div', { class: this.sizeClass }, msg)
      );

      var child = [];

      this.label && child.push(
        h('div', {
          staticClass: 'q-message-label text-center',
          domProps: ( obj$1 = {}, obj$1[this.labelSanitize === true ? 'textContent' : 'innerHTML'] = this.label, obj$1 )
        })
      );

      child.push(
        h('div', { class: this.containerClass }, container)
      );

      return h('div', {
        class: ("q-message q-message-" + (this.op)),
        on: this.$listeners
      }, child)
    }
  });

  var OptionSizeMixin = getSizeMixin({
    xs: 30,
    sm: 35,
    md: 40,
    lg: 50,
    xl: 60
  });

  var RefocusTargetMixin = {
    computed: {
      __refocusTargetEl: function __refocusTargetEl () {
        if (this.disable !== true) {
          return this.$createElement('span', {
            ref: 'refocusTarget',
            staticClass: 'no-outline',
            attrs: { tabindex: -1 }
          })
        }
      }
    },

    methods: {
      __refocusTarget: function __refocusTarget (e) {
        if (e !== void 0 && e.type.indexOf('key') === 0) {
          if (document.activeElement !== this.$el && this.$el.contains(document.activeElement) === true) {
            this.$el.focus();
          }
        }
        else if ((e === void 0 || this.$el.contains(e.target) === true) && this.$refs.refocusTarget !== void 0) {
          this.$refs.refocusTarget.focus();
        }
      }
    }
  };

  var CheckboxMixin = {
    mixins: [ DarkMixin, OptionSizeMixin, FormMixin, RefocusTargetMixin ],

    props: {
      value: {
        required: true,
        default: null
      },
      val: {},

      trueValue: { default: true },
      falseValue: { default: false },

      toggleIndeterminate: Boolean,
      indeterminateValue: { default: null },

      label: String,
      leftLabel: Boolean,
      fontSize: String,

      color: String,
      keepColor: Boolean,
      dense: Boolean,

      disable: Boolean,
      tabindex: [String, Number]
    },

    computed: {
      isTrue: function isTrue () {
        return this.modelIsArray === true
          ? this.index > -1
          : this.value === this.trueValue
      },

      isFalse: function isFalse () {
        return this.modelIsArray === true
          ? this.index === -1
          : this.value === this.falseValue
      },

      isIndeterminate: function isIndeterminate () {
        return this.value === this.indeterminateValue &&
          this.value !== this.falseValue
      },

      index: function index () {
        if (this.modelIsArray === true) {
          return this.value.indexOf(this.val)
        }
      },

      modelIsArray: function modelIsArray () {
        return this.val !== void 0 && Array.isArray(this.value)
      },

      computedTabindex: function computedTabindex () {
        return this.disable === true ? -1 : this.tabindex || 0
      },

      labelStyle: function labelStyle () {
        if (this.fontSize !== void 0) {
          return { fontSize: this.fontSize }
        }
      },

      classes: function classes () {
        return "q-" + (this.type) + " cursor-pointer no-outline row inline no-wrap items-center" +
          (this.disable === true ? ' disabled' : '') +
          (this.isDark === true ? (" q-" + (this.type) + "--dark") : '') +
          (this.dense === true ? (" q-" + (this.type) + "--dense") : '') +
          (this.leftLabel === true ? ' reverse' : '')
      },

      innerClass: function innerClass () {
        var state = this.isTrue === true ? 'truthy' : (this.isFalse === true ? 'falsy' : 'indet');
        var color = this.color !== void 0 && (
          this.keepColor === true ||
          (this.type === 'toggle' ? this.isTrue === true : this.isFalse !== true)
        )
          ? (" text-" + (this.color))
          : '';

        return ("q-" + (this.type) + "__inner--" + state + color)
      },

      formAttrs: function formAttrs () {
        var prop = { type: 'checkbox' };

        this.name !== void 0 && Object.assign(prop, {
          checked: this.isTrue,
          name: this.name,
          value: this.modelIsArray === true
            ? this.val
            : this.trueValue
        });

        return prop
      },

      attrs: function attrs () {
        var attrs = {
          tabindex: this.computedTabindex,
          role: 'checkbox',
          'aria-label': this.label,
          'aria-checked': this.isIndeterminate === true
            ? 'mixed'
            : this.isTrue === true ? 'true' : 'false'
        };

        if (this.disable === true) {
          attrs['aria-disabled'] = '';
        }

        return attrs
      }
    },

    methods: {
      toggle: function toggle (e) {
        if (e !== void 0) {
          stopAndPrevent(e);
          this.__refocusTarget(e);
        }

        if (this.disable === true) {
          return
        }

        var val;

        if (this.modelIsArray === true) {
          if (this.isTrue === true) {
            val = this.value.slice();
            val.splice(this.index, 1);
          }
          else {
            val = this.value.concat([ this.val ]);
          }
        }
        else if (this.isTrue === true) {
          val = this.toggleIndeterminate === true
            ? this.indeterminateValue
            : this.falseValue;
        }
        else if (this.isFalse === true) {
          val = this.trueValue;
        }
        else {
          val = this.falseValue;
        }

        this.$emit('input', val);
      },

      __onKeydown: function __onKeydown (e) {
        if (e.keyCode === 13 || e.keyCode === 32) {
          stopAndPrevent(e);
        }
      },

      __onKeyup: function __onKeyup (e) {
        if (e.keyCode === 13 || e.keyCode === 32) {
          this.toggle(e);
        }
      }
    },

    render: function render (h) {
      var inner = this.__getInner(h);

      this.disable !== true && this.__injectFormInput(
        inner,
        'unshift',
        ("q-" + (this.type) + "__native absolute q-ma-none q-pa-none invisible")
      );

      var child = [
        h('div', {
          staticClass: ("q-" + (this.type) + "__inner relative-position no-pointer-events"),
          class: this.innerClass,
          style: this.sizeStyle
        }, inner)
      ];

      if (this.__refocusTargetEl !== void 0) {
        child.push(this.__refocusTargetEl);
      }

      var label = this.label !== void 0
        ? mergeSlot([ this.label ], this, 'default')
        : slot(this, 'default');

      label !== void 0 && child.push(
        h('div', {
          staticClass: ("q-" + (this.type) + "__label q-anchor--skip")
        }, label)
      );

      return h('div', {
        class: this.classes,
        attrs: this.attrs,
        on: cache(this, 'inpExt', {
          click: this.toggle,
          keydown: this.__onKeydown,
          keyup: this.__onKeyup
        })
      }, child)
    }
  };

  var QCheckbox = Vue.extend({
    name: 'QCheckbox',

    mixins: [ CheckboxMixin ],

    methods: {
      __getInner: function __getInner (h) {
        return [
          h('div', {
            staticClass: 'q-checkbox__bg absolute'
          }, [
            h('svg', {
              staticClass: 'q-checkbox__svg fit absolute-full',
              attrs: { focusable: 'false' /* needed for IE11 */, viewBox: '0 0 24 24' }
            }, [
              h('path', {
                staticClass: 'q-checkbox__truthy',
                attrs: {
                  fill: 'none',
                  d: 'M1.73,12.91 8.1,19.28 22.79,4.59'
                }
              }),

              h('path', {
                staticClass: 'q-checkbox__indet',
                attrs: {
                  d: 'M4,14H20V10H4'
                }
              })
            ])
          ])
        ]
      }
    },

    created: function created () {
      this.type = 'checkbox';
    }
  });

  var QChip = Vue.extend({
    name: 'QChip',

    mixins: [
      RippleMixin,
      DarkMixin,
      getSizeMixin({
        xs: 8,
        sm: 10,
        md: 14,
        lg: 20,
        xl: 24
      })
    ],

    model: {
      event: 'remove'
    },

    props: {
      dense: Boolean,

      icon: String,
      iconRight: String,
      label: [String, Number],

      color: String,
      textColor: String,

      value: {
        type: Boolean,
        default: true
      },
      selected: {
        type: Boolean,
        default: null
      },

      square: Boolean,
      outline: Boolean,
      clickable: Boolean,
      removable: Boolean,

      tabindex: [String, Number],
      disable: Boolean
    },

    computed: {
      classes: function classes () {
        var obj;

        var text = this.outline === true
          ? this.color || this.textColor
          : this.textColor;

        return ( obj = {}, obj[("bg-" + (this.color))] = this.outline === false && this.color !== void 0, obj[("text-" + text + " q-chip--colored")] = text, obj.disabled = this.disable, obj['q-chip--dense'] = this.dense, obj['q-chip--outline'] = this.outline, obj['q-chip--selected'] = this.selected, obj['q-chip--clickable cursor-pointer non-selectable q-hoverable'] = this.isClickable, obj['q-chip--square'] = this.square, obj['q-chip--dark q-dark'] = this.isDark, obj )
      },

      hasLeftIcon: function hasLeftIcon () {
        return this.selected === true || this.icon !== void 0
      },

      isClickable: function isClickable () {
        return this.disable === false && (this.clickable === true || this.selected !== null)
      },

      computedTabindex: function computedTabindex () {
        return this.disable === true ? -1 : this.tabindex || 0
      }
    },

    methods: {
      __onKeyup: function __onKeyup (e) {
        e.keyCode === 13 /* ENTER */ && this.__onClick(e);
      },

      __onClick: function __onClick (e) {
        if (!this.disable) {
          this.$emit('update:selected', !this.selected);
          this.$emit('click', e);
        }
      },

      __onRemove: function __onRemove (e) {
        if (e.keyCode === void 0 || e.keyCode === 13) {
          stopAndPrevent(e);
          !this.disable && this.$emit('remove', false);
        }
      },

      __getContent: function __getContent (h) {
        var child = [];

        this.isClickable === true && child.push(
          h('div', { staticClass: 'q-focus-helper' })
        );

        this.hasLeftIcon === true && child.push(
          h(QIcon, {
            staticClass: 'q-chip__icon q-chip__icon--left',
            props: { name: this.selected === true ? this.$q.iconSet.chip.selected : this.icon }
          })
        );

        var label = this.label !== void 0
          ? [ h('div', { staticClass: 'ellipsis' }, [ this.label ]) ]
          : void 0;

        child.push(
          h('div', {
            staticClass: 'q-chip__content col row no-wrap items-center q-anchor--skip'
          }, mergeSlotSafely(label, this, 'default'))
        );

        this.iconRight && child.push(
          h(QIcon, {
            staticClass: 'q-chip__icon q-chip__icon--right',
            props: { name: this.iconRight }
          })
        );

        this.removable && child.push(
          h(QIcon, {
            staticClass: 'q-chip__icon q-chip__icon--remove cursor-pointer',
            props: { name: this.$q.iconSet.chip.remove },
            attrs: { tabindex: this.computedTabindex },
            nativeOn: {
              click: this.__onRemove,
              keyup: this.__onRemove
            }
          })
        );

        return child
      }
    },

    render: function render (h) {
      if (this.value === false) { return }

      var data = {
        staticClass: 'q-chip row inline no-wrap items-center',
        class: this.classes,
        style: this.sizeStyle
      };

      this.isClickable === true && Object.assign(data, {
        attrs: { tabindex: this.computedTabindex },
        on: cache(this, 'click', {
          click: this.__onClick,
          keyup: this.__onKeyup
        }),
        directives: cache(this, 'dir#' + this.ripple, [
          { name: 'ripple', value: this.ripple }
        ])
      });

      return h('div', data, this.__getContent(h))
    }
  });

  var
    radius = 50,
    diameter = 2 * radius,
    circumference = diameter * Math.PI,
    strokeDashArray = Math.round(circumference * 1000) / 1000;

  var QCircularProgress = Vue.extend({
    name: 'QCircularProgress',

    mixins: [ SizeMixin ],

    props: {
      value: {
        type: Number,
        default: 0
      },

      min: {
        type: Number,
        default: 0
      },
      max: {
        type: Number,
        default: 100
      },

      color: String,
      centerColor: String,
      trackColor: String,

      fontSize: String,

      // ratio
      thickness: {
        type: Number,
        default: 0.2,
        validator: function (v) { return v >= 0 && v <= 1; }
      },

      angle: {
        type: Number,
        default: 0
      },

      indeterminate: Boolean,
      showValue: Boolean,
      reverse: Boolean,

      instantFeedback: Boolean // used by QKnob, private
    },

    computed: {
      svgStyle: function svgStyle () {
        return { transform: ("rotate3d(0, 0, 1, " + (this.angle - 90) + "deg)") }
      },

      circleStyle: function circleStyle () {
        if (this.instantFeedback !== true && this.indeterminate !== true) {
          return { transition: 'stroke-dashoffset 0.6s ease 0s, stroke 0.6s ease' }
        }
      },

      dir: function dir () {
        return (this.$q.lang.rtl === true ? -1 : 1) * (this.reverse ? -1 : 1)
      },

      viewBox: function viewBox () {
        return diameter / (1 - this.thickness / 2)
      },

      viewBoxAttr: function viewBoxAttr () {
        return ((this.viewBox / 2) + " " + (this.viewBox / 2) + " " + (this.viewBox) + " " + (this.viewBox))
      },

      strokeDashOffset: function strokeDashOffset () {
        var progress = 1 - (this.value - this.min) / (this.max - this.min);
        return (this.dir * progress) * circumference
      },

      strokeWidth: function strokeWidth () {
        return this.thickness / 2 * this.viewBox
      },

      attrs: function attrs () {
        return {
          role: 'progressbar',
          'aria-valuemin': this.min,
          'aria-valuemax': this.max,
          'aria-valuenow': this.indeterminate === true ? void 0 : this.value
        }
      }
    },

    methods: {
      __getCircle: function __getCircle (h, ref) {
        var thickness = ref.thickness;
        var offset = ref.offset;
        var color = ref.color;
        var cls = ref.cls;

        return h('circle', {
          staticClass: 'q-circular-progress__' + cls,
          class: color !== void 0 ? ("text-" + color) : null,
          style: this.circleStyle,
          attrs: {
            fill: 'transparent',
            stroke: 'currentColor',
            'stroke-width': thickness,
            'stroke-dasharray': strokeDashArray,
            'stroke-dashoffset': offset,
            cx: this.viewBox,
            cy: this.viewBox,
            r: radius
          }
        })
      }
    },

    render: function render (h) {
      var svgChild = [];

      this.centerColor !== void 0 && this.centerColor !== 'transparent' && svgChild.push(
        h('circle', {
          staticClass: 'q-circular-progress__center',
          class: ("text-" + (this.centerColor)),
          attrs: {
            fill: 'currentColor',
            r: radius - this.strokeWidth / 2,
            cx: this.viewBox,
            cy: this.viewBox
          }
        })
      );

      this.trackColor !== void 0 && this.trackColor !== 'transparent' && svgChild.push(
        this.__getCircle(h, {
          cls: 'track',
          thickness: this.strokeWidth,
          offset: 0,
          color: this.trackColor
        })
      );

      svgChild.push(
        this.__getCircle(h, {
          cls: 'circle',
          thickness: this.strokeWidth,
          offset: this.strokeDashOffset,
          color: this.color
        })
      );

      var child = [
        h('svg', {
          staticClass: 'q-circular-progress__svg',
          style: this.svgStyle,
          attrs: {
            focusable: 'false' /* needed for IE11 */,
            viewBox: this.viewBoxAttr
          }
        }, svgChild)
      ];

      this.showValue === true && child.push(
        h('div', {
          staticClass: 'q-circular-progress__text absolute-full row flex-center content-center',
          style: { fontSize: this.fontSize }
        }, this.$scopedSlots.default !== void 0 ? this.$scopedSlots.default() : [ h('div', [ this.value ]) ])
      );

      return h('div', {
        staticClass: 'q-circular-progress',
        class: ("q-circular-progress--" + (this.indeterminate === true ? 'in' : '') + "determinate"),
        style: this.sizeStyle,
        on: this.$listeners,
        attrs: this.attrs
      }, mergeSlotSafely(child, this, 'internal'))
    }
  });

  // file referenced from docs

  var
    hex = /^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$/,
    hexa = /^#[0-9a-fA-F]{4}([0-9a-fA-F]{4})?$/,
    hexOrHexa = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/,
    rgb = /^rgb\(((0|[1-9][\d]?|1[\d]{0,2}|2[\d]?|2[0-4][\d]|25[0-5]),){2}(0|[1-9][\d]?|1[\d]{0,2}|2[\d]?|2[0-4][\d]|25[0-5])\)$/,
    rgba = /^rgba\(((0|[1-9][\d]?|1[\d]{0,2}|2[\d]?|2[0-4][\d]|25[0-5]),){2}(0|[1-9][\d]?|1[\d]{0,2}|2[\d]?|2[0-4][\d]|25[0-5]),(0|0\.[0-9]+[1-9]|0\.[1-9]+|1)\)$/;

  var testPattern = {
    date: function (v) { return /^-?[\d]+\/[0-1]\d\/[0-3]\d$/.test(v); },
    time: function (v) { return /^([0-1]?\d|2[0-3]):[0-5]\d$/.test(v); },
    fulltime: function (v) { return /^([0-1]?\d|2[0-3]):[0-5]\d:[0-5]\d$/.test(v); },
    timeOrFulltime: function (v) { return /^([0-1]?\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/.test(v); },

    hexColor: function (v) { return hex.test(v); },
    hexaColor: function (v) { return hexa.test(v); },
    hexOrHexaColor: function (v) { return hexOrHexa.test(v); },

    rgbColor: function (v) { return rgb.test(v); },
    rgbaColor: function (v) { return rgba.test(v); },
    rgbOrRgbaColor: function (v) { return rgb.test(v) || rgba.test(v); },

    hexOrRgbColor: function (v) { return hex.test(v) || rgb.test(v); },
    hexaOrRgbaColor: function (v) { return hexa.test(v) || rgba.test(v); },
    anyColor: function (v) { return hexOrHexa.test(v) || rgb.test(v) || rgba.test(v); }
  };

  var patterns = {
    testPattern: testPattern
  };

  function throttle (fn, limit) {
    if ( limit === void 0 ) limit = 250;

    var wait = false, result;

    return function (/* ...args */) {
      if (wait === false) {
        wait = true;
        setTimeout(function () { wait = false; }, limit);
        result = fn.apply(this, arguments);
      }

      return result
    }
  }

  function getChanges (evt, ctx, isFinal) {
    var
      pos = position(evt),
      dir,
      distX = pos.left - ctx.event.x,
      distY = pos.top - ctx.event.y,
      absX = Math.abs(distX),
      absY = Math.abs(distY);

    var direction = ctx.direction;

    if (direction.horizontal === true && direction.vertical !== true) {
      dir = distX < 0 ? 'left' : 'right';
    }
    else if (direction.horizontal !== true && direction.vertical === true) {
      dir = distY < 0 ? 'up' : 'down';
    }
    else if (direction.up === true && distY < 0) {
      dir = 'up';
      if (absX > absY) {
        if (direction.left === true && distX < 0) {
          dir = 'left';
        }
        else if (direction.right === true && distX > 0) {
          dir = 'right';
        }
      }
    }
    else if (direction.down === true && distY > 0) {
      dir = 'down';
      if (absX > absY) {
        if (direction.left === true && distX < 0) {
          dir = 'left';
        }
        else if (direction.right === true && distX > 0) {
          dir = 'right';
        }
      }
    }
    else if (direction.left === true && distX < 0) {
      dir = 'left';
      if (absX < absY) {
        if (direction.up === true && distY < 0) {
          dir = 'up';
        }
        else if (direction.down === true && distY > 0) {
          dir = 'down';
        }
      }
    }
    else if (direction.right === true && distX > 0) {
      dir = 'right';
      if (absX < absY) {
        if (direction.up === true && distY < 0) {
          dir = 'up';
        }
        else if (direction.down === true && distY > 0) {
          dir = 'down';
        }
      }
    }

    var synthetic = false;

    if (dir === void 0 && isFinal !== true) {
      if (ctx.event.isFirst === true || ctx.event.lastDir === void 0) {
        return {}
      }

      dir = ctx.event.lastDir;
      synthetic = true;

      if (dir === 'left' || dir === 'right') {
        pos.left -= distX;
        absX = 0;
        distX = 0;
      }
      else {
        pos.top -= distY;
        absY = 0;
        distY = 0;
      }
    }

    return {
      synthetic: synthetic,
      payload: {
        evt: evt,
        touch: ctx.event.mouse !== true,
        mouse: ctx.event.mouse === true,
        position: pos,
        direction: dir,
        isFirst: ctx.event.isFirst,
        isFinal: isFinal === true,
        duration: Date.now() - ctx.event.time,
        distance: {
          x: absX,
          y: absY
        },
        offset: {
          x: distX,
          y: distY
        },
        delta: {
          x: pos.left - ctx.event.lastX,
          y: pos.top - ctx.event.lastY
        }
      }
    }
  }

  var uid = 0;

  var TouchPan = {
    name: 'touch-pan',

    bind: function bind (el, ref) {
      var value = ref.value;
      var modifiers = ref.modifiers;

      // early return, we don't need to do anything
      if (modifiers.mouse !== true && client.has.touch !== true) {
        return
      }

      function handleEvent (evt, mouseEvent) {
        if (modifiers.mouse === true && mouseEvent === true) {
          stopAndPrevent(evt);
        }
        else {
          modifiers.stop === true && stop(evt);
          modifiers.prevent === true && prevent(evt);
        }
      }

      var ctx = {
        uid: 'qvtp_' + (uid++),
        handler: value,
        modifiers: modifiers,
        direction: getModifierDirections(modifiers),

        noop: noop,

        mouseStart: function mouseStart (evt) {
          if (shouldStart(evt, ctx) && leftClick(evt)) {
            addEvt(ctx, 'temp', [
              [ document, 'mousemove', 'move', 'notPassiveCapture' ],
              [ document, 'mouseup', 'end', 'passiveCapture' ]
            ]);

            ctx.start(evt, true);
          }
        },

        touchStart: function touchStart (evt) {
          if (shouldStart(evt, ctx)) {
            var target = getTouchTarget(evt.target);

            addEvt(ctx, 'temp', [
              [ target, 'touchmove', 'move', 'notPassiveCapture' ],
              [ target, 'touchcancel', 'end', 'passiveCapture' ],
              [ target, 'touchend', 'end', 'passiveCapture' ]
            ]);

            ctx.start(evt);
          }
        },

        start: function start (evt, mouseEvent) {
          client.is.firefox === true && preventDraggable(el, true);
          ctx.lastEvt = evt;

          var pos = position(evt);

          /*
           * Stop propagation so possible upper v-touch-pan don't catch this as well;
           * If we're not the target (based on modifiers), we'll re-emit the event later
           */
          if (mouseEvent === true || modifiers.stop === true) {
            /*
             * are we directly switching to detected state?
             * clone event only otherwise
             */
            if (
              ctx.direction.all !== true &&
              (mouseEvent !== true || ctx.direction.mouseAllDir !== true)
            ) {
              var clone = evt.type.indexOf('mouse') > -1
                ? new MouseEvent(evt.type, evt)
                : new TouchEvent(evt.type, evt);

              evt.defaultPrevented === true && prevent(clone);
              evt.cancelBubble === true && stop(clone);

              clone.qClonedBy = evt.qClonedBy === void 0
                ? [ctx.uid]
                : evt.qClonedBy.concat(ctx.uid);
              clone.qKeyEvent = evt.qKeyEvent;
              clone.qClickOutside = evt.qClickOutside;

              ctx.initialEvent = {
                target: evt.target,
                event: clone
              };
            }

            stop(evt);
          }

          ctx.event = {
            x: pos.left,
            y: pos.top,
            time: Date.now(),
            mouse: mouseEvent === true,
            detected: false,
            isFirst: true,
            isFinal: false,
            lastX: pos.left,
            lastY: pos.top
          };
        },

        move: function move (evt) {
          if (ctx.event === void 0) {
            return
          }

          ctx.lastEvt = evt;

          var isMouseEvt = ctx.event.mouse === true;
          var start = function () {
            handleEvent(evt, isMouseEvt);

            document.documentElement.style.cursor = 'grabbing';
            isMouseEvt === true && document.body.classList.add('no-pointer-events');
            document.body.classList.add('non-selectable');
            clearSelection();

            ctx.styleCleanup = function (withDelay) {
              ctx.styleCleanup = void 0;

              document.documentElement.style.cursor = '';
              document.body.classList.remove('non-selectable');

              if (isMouseEvt === true) {
                var remove = function () {
                  document.body.classList.remove('no-pointer-events');
                };

                if (withDelay === true) { setTimeout(remove, 50); }
                else { remove(); }
              }
            };
          };

          if (ctx.event.detected === true) {
            ctx.event.isFirst !== true && handleEvent(evt, ctx.event.mouse);

            var ref = getChanges(evt, ctx, false);
            var payload = ref.payload;
            var synthetic = ref.synthetic;

            if (payload !== void 0) {
              if (ctx.handler(payload) === false) {
                ctx.end(evt);
              }
              else {
                if (ctx.styleCleanup === void 0 && ctx.event.isFirst === true) {
                  start();
                }

                ctx.event.lastX = payload.position.left;
                ctx.event.lastY = payload.position.top;
                ctx.event.lastDir = synthetic === true ? void 0 : payload.direction;
                ctx.event.isFirst = false;
              }
            }

            return
          }

          if (
            ctx.direction.all === true ||
            (isMouseEvt === true && ctx.modifiers.mouseAllDir === true)
          ) {
            start();
            ctx.event.detected = true;
            ctx.move(evt);
            return
          }

          var
            pos = position(evt),
            distX = pos.left - ctx.event.x,
            distY = pos.top - ctx.event.y,
            absX = Math.abs(distX),
            absY = Math.abs(distY);

          if (absX !== absY) {
            if (
              (ctx.direction.horizontal === true && absX > absY) ||
              (ctx.direction.vertical === true && absX < absY) ||
              (ctx.direction.up === true && absX < absY && distY < 0) ||
              (ctx.direction.down === true && absX < absY && distY > 0) ||
              (ctx.direction.left === true && absX > absY && distX < 0) ||
              (ctx.direction.right === true && absX > absY && distX > 0)
            ) {
              ctx.event.detected = true;
              ctx.move(evt);
            }
            else {
              ctx.end(evt, true);
            }
          }
        },

        end: function end (evt, abort) {
          if (ctx.event === void 0) {
            return
          }

          cleanEvt(ctx, 'temp');
          client.is.firefox === true && preventDraggable(el, false);
          ctx.styleCleanup !== void 0 && ctx.styleCleanup(true);

          if (abort === true) {
            if (ctx.event.detected !== true && ctx.initialEvent !== void 0) {
              ctx.initialEvent.target.dispatchEvent(ctx.initialEvent.event);
            }
          }
          else if (ctx.event.detected === true) {
            ctx.event.isFirst === true && ctx.handler(getChanges(evt === void 0 ? ctx.lastEvt : evt, ctx).payload);
            ctx.handler(getChanges(evt === void 0 ? ctx.lastEvt : evt, ctx, true).payload);
          }

          ctx.event = void 0;
          ctx.initialEvent = void 0;
          ctx.lastEvt = void 0;
        }
      };

      if (el.__qtouchpan) {
        el.__qtouchpan_old = el.__qtouchpan;
      }

      el.__qtouchpan = ctx;

      modifiers.mouse === true && addEvt(ctx, 'main', [
        [ el, 'mousedown', 'mouseStart', ("passive" + (modifiers.mouseCapture === true ? 'Capture' : '')) ]
      ]);

      client.has.touch === true && addEvt(ctx, 'main', [
        [ el, 'touchstart', 'touchStart', ("passive" + (modifiers.capture === true ? 'Capture' : '')) ],
        [ el, 'touchmove', 'noop', 'notPassiveCapture' ]
      ]);
    },

    update: function update (el, binding) {
      el.__qtouchpan !== void 0 && updateModifiers(el.__qtouchpan, binding);
    },

    unbind: function unbind (el) {
      var ctx = el.__qtouchpan_old || el.__qtouchpan;

      if (ctx !== void 0) {
        cleanEvt(ctx, 'main');
        cleanEvt(ctx, 'temp');

        client.is.firefox === true && preventDraggable(el, false);
        ctx.styleCleanup !== void 0 && ctx.styleCleanup();

        delete el[el.__qtouchpan_old ? '__qtouchpan_old' : '__qtouchpan'];
      }
    }
  };

  // PGDOWN, LEFT, DOWN, PGUP, RIGHT, UP
  var keyCodes = [34, 37, 40, 33, 39, 38];

  function getRatio (evt, dragging, reverse) {
    var
      pos = position(evt),
      val = between((pos.left - dragging.left) / dragging.width, 0, 1);

    return reverse === true ? 1.0 - val : val
  }

  function getModel (ratio, min, max, step, decimals) {
    var model = min + ratio * (max - min);

    if (step > 0) {
      var modulo = (model - min) % step;
      model += (Math.abs(modulo) >= step / 2 ? (modulo < 0 ? -1 : 1) * step : 0) - modulo;
    }

    if (decimals > 0) {
      model = parseFloat(model.toFixed(decimals));
    }

    return between(model, min, max)
  }

  var SliderMixin = {
    mixins: [ DarkMixin, FormMixin ],

    directives: {
      TouchPan: TouchPan
    },

    props: {
      min: {
        type: Number,
        default: 0
      },
      max: {
        type: Number,
        default: 100
      },
      step: {
        type: Number,
        default: 1,
        validator: function (v) { return v >= 0; }
      },

      color: String,

      labelColor: String,
      labelTextColor: String,
      dense: Boolean,

      label: Boolean,
      labelAlways: Boolean,
      markers: Boolean,
      snap: Boolean,

      reverse: Boolean,

      disable: Boolean,
      readonly: Boolean,
      tabindex: [String, Number],

      thumbPath: {
        type: String,
        default: 'M 4, 10 a 6,6 0 1,0 12,0 a 6,6 0 1,0 -12,0'
      }
    },

    data: function data () {
      return {
        active: false,
        preventFocus: false,
        focus: false
      }
    },

    computed: {
      classes: function classes () {
        return "q-slider q-slider--" + (this.active === true ? '' : 'in') + "active" +
          (this.isReversed === true ? ' q-slider--reversed' : '') +
          (this.color !== void 0 ? (" text-" + (this.color)) : '') +
          (this.disable === true ? ' disabled' : '') +
          (this.editable === true ? ' q-slider--editable' : '') +
          (this.focus === 'both' ? ' q-slider--focus' : '') +
          (this.label || this.labelAlways === true ? ' q-slider--label' : '') +
          (this.labelAlways === true ? ' q-slider--label-always' : '') +
          (this.isDark === true ? ' q-slider--dark' : '') +
          (this.dense === true ? ' q-slider--dense' : '')
      },

      editable: function editable () {
        return !this.disable && !this.readonly
      },

      decimals: function decimals () {
        return (String(this.step).trim('0').split('.')[1] || '').length
      },

      computedStep: function computedStep () {
        return this.step === 0 ? 1 : this.step
      },

      markerStyle: function markerStyle () {
        return {
          backgroundSize: 100 * this.computedStep / (this.max - this.min) + '% 2px'
        }
      },

      computedTabindex: function computedTabindex () {
        return this.editable === true ? this.tabindex || 0 : -1
      },

      isReversed: function isReversed () {
        return this.reverse !== (this.$q.lang.rtl === true)
      },

      horizProp: function horizProp () {
        return this.isReversed === true ? 'right' : 'left'
      },

      attrs: function attrs () {
        var attrs = {
          role: 'slider',
          'aria-valuemin': this.min,
          'aria-valuemax': this.max,
          'aria-orientation': 'horizontal',
          'data-step': this.step
        };

        if (this.disable === true) {
          attrs['aria-disabled'] = '';
        }

        return attrs
      }
    },

    methods: {
      __getThumbSvg: function __getThumbSvg (h) {
        return h('svg', {
          staticClass: 'q-slider__thumb absolute',
          attrs: { focusable: 'false' /* needed for IE11 */, viewBox: '0 0 20 20', width: '20', height: '20' }
        }, [
          h('path', {
            attrs: {
              d: this.thumbPath
            }
          })
        ])
      },

      __getPinStyle: function __getPinStyle (percent, ratio) {
        var obj;

        var offset = (Math.ceil(20 * Math.abs(0.5 - ratio))) + "px";
        return {
          pin: {
            transformOrigin: ((this.$q.lang.rtl === true ? offset : (this.$q.platform.is.ie === true ? '100%' : ("calc(100% - " + offset + ")"))) + " 50%")
          },

          pinTextContainer: ( obj = {}, obj[this.$q.lang.rtl === true ? 'left' : 'right'] = ((percent * 100) + "%"), obj.transform = ("translateX(" + (Math.ceil((this.$q.lang.rtl === true ? -1 : 1) * 20 * percent)) + "px)"), obj )
        }
      },

      __pan: function __pan (event) {
        if (event.isFinal) {
          if (this.dragging) {
            this.__updatePosition(event.evt);
            // only if touch, because we also have mousedown/up:
            event.touch === true && this.__updateValue(true);
            this.dragging = false;
          }
          this.active = false;
        }
        else if (event.isFirst) {
          this.dragging = this.__getDragging(event.evt);
          this.__updatePosition(event.evt);
          this.__updateValue();
          this.active = true;
        }
        else {
          this.__updatePosition(event.evt);
          this.__updateValue();
        }
      },

      __blur: function __blur () {
        this.focus = false;
      },

      __activate: function __activate (evt) {
        this.__updatePosition(evt, this.__getDragging(evt));
        this.__updateValue();

        this.preventFocus = true;
        this.active = true;

        document.addEventListener('mouseup', this.__deactivate, true);
      },

      __deactivate: function __deactivate () {
        this.preventFocus = false;
        this.active = false;

        this.__updateValue(true);
        this.__blur();

        document.removeEventListener('mouseup', this.__deactivate, true);
      },

      __mobileClick: function __mobileClick (evt) {
        this.__updatePosition(evt, this.__getDragging(evt));
        this.__updateValue(true);
      },

      __keyup: function __keyup (evt) {
        if (keyCodes.includes(evt.keyCode)) {
          this.__updateValue(true);
        }
      }
    },

    beforeDestroy: function beforeDestroy () {
      document.removeEventListener('mouseup', this.__deactivate, true);
    }
  };

  var QSlider = Vue.extend({
    name: 'QSlider',

    mixins: [ SliderMixin ],

    props: {
      value: {
        required: true,
        default: null,
        validator: function (v) { return typeof v === 'number' || v === null; }
      },

      labelValue: [String, Number]
    },

    data: function data () {
      return {
        model: this.value === null ? this.min : this.value,
        curRatio: 0
      }
    },

    watch: {
      value: function value (v) {
        this.model = v === null
          ? 0
          : between(v, this.min, this.max);
      },

      min: function min (v) {
        this.model = between(this.model, v, this.max);
      },

      max: function max (v) {
        this.model = between(this.model, this.min, v);
      }
    },

    computed: {
      ratio: function ratio () {
        return this.active === true ? this.curRatio : this.modelRatio
      },

      modelRatio: function modelRatio () {
        return (this.model - this.min) / (this.max - this.min)
      },

      trackStyle: function trackStyle () {
        var obj;

        return ( obj = {}, obj[this.horizProp] = 0, obj.width = 100 * this.ratio + '%', obj )
      },

      thumbStyle: function thumbStyle () {
        var obj;

        return ( obj = {}, obj[this.horizProp] = (100 * this.ratio) + '%', obj )
      },

      thumbClass: function thumbClass () {
        if (this.preventFocus === false && this.focus === true) {
          return 'q-slider--focus'
        }
      },

      pinClass: function pinClass () {
        if (this.labelColor !== void 0) {
          return ("text-" + (this.labelColor))
        }
      },

      pinTextClass: function pinTextClass () {
        return 'q-slider__pin-value-marker-text' +
          (this.labelTextColor !== void 0 ? (" text-" + (this.labelTextColor)) : '')
      },

      events: function events () {
        if (this.editable === true) {
          return this.$q.platform.is.mobile === true
            ? { click: this.__mobileClick }
            : {
              mousedown: this.__activate,
              focus: this.__focus,
              blur: this.__blur,
              keydown: this.__keydown,
              keyup: this.__keyup
            }
        }
      },

      computedLabel: function computedLabel () {
        return this.labelValue !== void 0
          ? this.labelValue
          : this.model
      },

      pinStyle: function pinStyle () {
        var percent = (this.reverse === true ? -this.ratio : this.ratio - 1);
        return this.__getPinStyle(percent, this.ratio)
      }
    },

    methods: {
      __updateValue: function __updateValue (change) {
        if (this.model !== this.value) {
          this.$emit('input', this.model);
        }
        change === true && this.$emit('change', this.model);
      },

      __getDragging: function __getDragging () {
        return this.$el.getBoundingClientRect()
      },

      __updatePosition: function __updatePosition (event, dragging) {
        if ( dragging === void 0 ) dragging = this.dragging;

        var ratio = getRatio(
          event,
          dragging,
          this.isReversed
        );

        this.model = getModel(ratio, this.min, this.max, this.step, this.decimals);
        this.curRatio = this.snap !== true || this.step === 0
          ? ratio
          : (this.model - this.min) / (this.max - this.min);
      },

      __focus: function __focus () {
        this.focus = true;
      },

      __keydown: function __keydown (evt) {
        if (!keyCodes.includes(evt.keyCode)) {
          return
        }

        stopAndPrevent(evt);

        var
          step = ([34, 33].includes(evt.keyCode) ? 10 : 1) * this.computedStep,
          offset = [34, 37, 40].includes(evt.keyCode) ? -step : step;

        this.model = between(
          parseFloat((this.model + offset).toFixed(this.decimals)),
          this.min,
          this.max
        );

        this.__updateValue();
      }
    },

    render: function render (h) {
      var child = [
        this.__getThumbSvg(h),
        h('div', { staticClass: 'q-slider__focus-ring' })
      ];

      if (this.label === true || this.labelAlways === true) {
        child.push(
          h('div', {
            staticClass: 'q-slider__pin absolute',
            style: this.pinStyle.pin,
            class: this.pinClass
          }, [
            h('div', { staticClass: 'q-slider__pin-text-container', style: this.pinStyle.pinTextContainer }, [
              h('span', {
                staticClass: 'q-slider__pin-text',
                class: this.pinTextClass
              }, [
                this.computedLabel
              ])
            ])
          ]),

          h('div', {
            staticClass: 'q-slider__arrow',
            class: this.pinClass
          })
        );
      }

      if (this.name !== void 0 && this.disable !== true) {
        this.__injectFormInput(child, 'push');
      }

      var track = [
        h('div', {
          staticClass: 'q-slider__track absolute',
          style: this.trackStyle
        })
      ];

      this.markers === true && track.push(
        h('div', {
          staticClass: 'q-slider__track-markers absolute-full fit',
          style: this.markerStyle
        })
      );

      return h('div', {
        staticClass: this.value === null ? ' q-slider--no-value' : '',
        attrs: Object.assign({}, this.attrs,
          {'aria-valuenow': this.value,
          tabindex: this.computedTabindex}),
        class: this.classes,
        on: this.events,
        directives: this.editable === true ? cache(this, 'dir', [{
          name: 'touch-pan',
          value: this.__pan,
          modifiers: {
            horizontal: true,
            prevent: true,
            stop: true,
            mouse: true,
            mouseAllDir: true
          }
        }]) : null
      }, [
        h('div', {
          staticClass: 'q-slider__track-container absolute'
        }, track),

        h('div', {
          staticClass: 'q-slider__thumb-container absolute non-selectable',
          class: this.thumbClass,
          style: this.thumbStyle
        }, child)
      ])
    }
  });

  // using it to manage SSR rendering with best performance

  var CanRenderMixin = {
    data: function data () {
      return {
        canRender: !onSSR
      }
    },

    mounted: function mounted () {
      this.canRender === false && (this.canRender = true);
    }
  };

  var QResizeObserver = Vue.extend({
    name: 'QResizeObserver',

    mixins: [ CanRenderMixin ],

    props: {
      debounce: {
        type: [ String, Number ],
        default: 100
      }
    },

    data: function data () {
      return this.hasObserver === true
        ? {}
        : { url: this.$q.platform.is.ie === true ? null : 'about:blank' }
    },

    methods: {
      trigger: function trigger (now) {
        if (now === true || this.debounce === 0 || this.debounce === '0') {
          this.__onResize();
        }
        else if (!this.timer) {
          this.timer = setTimeout(this.__onResize, this.debounce);
        }
      },

      __onResize: function __onResize () {
        this.timer = null;

        if (!this.$el || !this.$el.parentNode) {
          return
        }

        var
          parent = this.$el.parentNode,
          size = {
            width: parent.offsetWidth,
            height: parent.offsetHeight
          };

        if (size.width === this.size.width && size.height === this.size.height) {
          return
        }

        this.size = size;
        this.$emit('resize', this.size);
      },

      __cleanup: function __cleanup () {
        if (this.curDocView !== void 0) {
          // iOS is fuzzy, need to check it first
          if (this.curDocView.removeEventListener !== void 0) {
            this.curDocView.removeEventListener('resize', this.trigger, listenOpts.passive);
          }
          this.curDocView = void 0;
        }
      },

      __onObjLoad: function __onObjLoad () {
        this.__cleanup();

        if (this.$el.contentDocument) {
          this.curDocView = this.$el.contentDocument.defaultView;
          this.curDocView.addEventListener('resize', this.trigger, listenOpts.passive);
        }

        this.__onResize();
      }
    },

    render: function render (h) {
      if (this.canRender === false || this.hasObserver === true) {
        return
      }

      return h('object', {
        style: this.style,
        attrs: {
          tabindex: -1, // fix for Firefox
          type: 'text/html',
          data: this.url,
          'aria-hidden': 'true'
        },
        on: cache(this, 'load', {
          load: this.__onObjLoad
        })
      })
    },

    beforeCreate: function beforeCreate () {
      this.size = { width: -1, height: -1 };
      if (isSSR === true) { return }

      this.hasObserver = typeof ResizeObserver !== 'undefined';

      if (this.hasObserver !== true) {
        this.style = (this.$q.platform.is.ie ? 'visibility:hidden;' : '') + "display:block;position:absolute;top:0;left:0;right:0;bottom:0;height:100%;width:100%;overflow:hidden;pointer-events:none;z-index:-1;";
      }
    },

    mounted: function mounted () {
      if (this.hasObserver === true) {
        this.observer = new ResizeObserver(this.trigger);
        this.observer.observe(this.$el.parentNode);
        this.__onResize();
        return
      }

      if (this.$q.platform.is.ie === true) {
        this.url = 'about:blank';
        this.__onResize();
      }
      else {
        this.__onObjLoad();
      }
    },

    beforeDestroy: function beforeDestroy () {
      clearTimeout(this.timer);

      if (this.hasObserver === true) {
        this.$el.parentNode && this.observer.unobserve(this.$el.parentNode);
        return
      }

      this.__cleanup();
    }
  });

  function getIndicatorClass (color, top, vertical) {
    var pos = vertical === true
      ? ['left', 'right']
      : ['top', 'bottom'];

    return ("absolute-" + (top === true ? pos[0] : pos[1]) + (color ? (" text-" + color) : ''))
  }

  function bufferPrioritySort (t1, t2) {
    if (t1.priorityMatched === t2.priorityMatched) {
      return t2.priorityHref - t1.priorityHref
    }
    return t2.priorityMatched - t1.priorityMatched
  }

  function bufferCleanSelected (t) {
    t.selected = false;
    return t
  }

  var
    bufferFilters = [
      function (t) { return t.selected === true && t.exact === true && t.redirected !== true },
      function (t) { return t.selected === true && t.exact === true },
      function (t) { return t.selected === true && t.redirected !== true },
      function (t) { return t.selected === true },
      function (t) { return t.exact === true && t.redirected !== true },
      function (t) { return t.redirected !== true },
      function (t) { return t.exact === true },
      function (t) { return true }
    ],
    bufferFiltersLen = bufferFilters.length;

  var QTabs = Vue.extend({
    name: 'QTabs',

    mixins: [ TimeoutMixin ],

    provide: function provide () {
      return {
        tabs: this.tabs,
        __recalculateScroll: this.__recalculateScroll,
        __activateTab: this.__activateTab,
        __activateRoute: this.__activateRoute
      }
    },

    props: {
      value: [Number, String],

      align: {
        type: String,
        default: 'center',
        validator: function (v) { return ['left', 'center', 'right', 'justify'].includes(v); }
      },
      breakpoint: {
        type: [String, Number],
        default: 600
      },

      vertical: Boolean,
      shrink: Boolean,
      stretch: Boolean,

      activeColor: String,
      activeBgColor: String,
      indicatorColor: String,
      leftIcon: String,
      rightIcon: String,

      switchIndicator: Boolean,

      narrowIndicator: Boolean,
      inlineLabel: Boolean,
      noCaps: Boolean,

      dense: Boolean
    },

    data: function data () {
      return {
        tabs: {
          current: this.value,
          activeColor: this.activeColor,
          activeBgColor: this.activeBgColor,
          indicatorClass: getIndicatorClass(
            this.indicatorColor,
            this.switchIndicator,
            this.vertical
          ),
          narrowIndicator: this.narrowIndicator,
          inlineLabel: this.inlineLabel,
          noCaps: this.noCaps
        },
        scrollable: false,
        leftArrow: true,
        rightArrow: false,
        justify: false
      }
    },

    watch: {
      value: function value (name) {
        this.__activateTab(name, true, true);
      },

      activeColor: function activeColor (v) {
        this.tabs.activeColor = v;
      },

      activeBgColor: function activeBgColor (v) {
        this.tabs.activeBgColor = v;
      },

      vertical: function vertical (v) {
        this.tabs.indicatorClass = getIndicatorClass(this.indicatorColor, this.switchIndicator, v);
      },

      indicatorColor: function indicatorColor (v) {
        this.tabs.indicatorClass = getIndicatorClass(v, this.switchIndicator, this.vertical);
      },

      switchIndicator: function switchIndicator (v) {
        this.tabs.indicatorClass = getIndicatorClass(this.indicatorColor, v, this.vertical);
      },

      narrowIndicator: function narrowIndicator (v) {
        this.tabs.narrowIndicator = v;
      },

      inlineLabel: function inlineLabel (v) {
        this.tabs.inlineLabel = v;
      },

      noCaps: function noCaps (v) {
        this.tabs.noCaps = v;
      }
    },

    computed: {
      alignClass: function alignClass () {
        var align = this.scrollable === true
          ? 'left'
          : (this.justify === true ? 'justify' : this.align);

        return ("q-tabs__content--align-" + align)
      },

      classes: function classes () {
        return "q-tabs--" + (this.scrollable === true ? '' : 'not-') + "scrollable" +
          " q-tabs--" + (this.vertical === true ? 'vertical' : 'horizontal') +
          (this.dense === true ? ' q-tabs--dense' : '') +
          (this.shrink === true ? ' col-shrink' : '') +
          (this.stretch === true ? ' self-stretch' : '')
      },

      domProps: function domProps () {
        return this.vertical === true
          ? { container: 'height', content: 'scrollHeight', posLeft: 'top', posRight: 'bottom' }
          : { container: 'width', content: 'scrollWidth', posLeft: 'left', posRight: 'right' }
      }
    },

    methods: {
      __activateTab: function __activateTab (name, setCurrent, skipEmit) {
        if (this.tabs.current !== name) {
          skipEmit !== true && this.$emit('input', name);
          if (setCurrent === true || this.$listeners.input === void 0) {
            this.__animate(this.tabs.current, name);
            this.tabs.current = name;
          }
        }
      },

      __activateRoute: function __activateRoute (params) {
        var this$1 = this;

        if (this.bufferRoute !== this.$route && this.buffer.length > 0) {
          clearTimeout(this.bufferTimer);
          this.bufferTimer = void 0;
          this.buffer.length = 0;
        }
        this.bufferRoute = this.$route;

        if (params !== void 0) {
          if (params.remove === true) {
            this.buffer = this.buffer.filter(function (t) { return t.name !== params.name; });
          }
          else {
            this.buffer.push(params);
          }
        }

        if (this.bufferTimer === void 0) {
          this.bufferTimer = setTimeout(function () {
            var tabs = [];

            for (var i = 0; i < bufferFiltersLen && tabs.length === 0; i++) {
              tabs = this$1.buffer.filter(bufferFilters[i]);
            }

            tabs.sort(bufferPrioritySort);
            this$1.__activateTab(tabs.length === 0 ? null : tabs[0].name, true);
            this$1.buffer = this$1.buffer.map(bufferCleanSelected);
            this$1.bufferTimer = void 0;
          }, 1);
        }
      },

      __recalculateScroll: function __recalculateScroll () {
        var this$1 = this;

        this.__nextTick(function () {
          this$1._isDestroyed !== true && this$1.__updateContainer({
            width: this$1.$el.offsetWidth,
            height: this$1.$el.offsetHeight
          });
        });

        this.__prepareTick();
      },

      __updateContainer: function __updateContainer (domSize) {
        var this$1 = this;

        var
          size = domSize[this.domProps.container],
          scrollSize = this.$refs.content[this.domProps.content],
          scroll = size > 0 && scrollSize > size; // when there is no tab, in Chrome, size === 0 and scrollSize === 1

        if (this.scrollable !== scroll) {
          this.scrollable = scroll;
        }

        // Arrows need to be updated even if the scroll status was already true
        scroll === true && this.$nextTick(function () { return this$1.__updateArrows(); });

        var justify = size < parseInt(this.breakpoint, 10);

        if (this.justify !== justify) {
          this.justify = justify;
        }
      },

      __animate: function __animate (oldName, newName) {
        var this$1 = this;

        var
          oldTab = oldName !== void 0 && oldName !== null && oldName !== ''
            ? this.$children.find(function (tab) { return tab.name === oldName; })
            : null,
          newTab = newName !== void 0 && newName !== null && newName !== ''
            ? this.$children.find(function (tab) { return tab.name === newName; })
            : null;

        if (oldTab && newTab) {
          var
            oldEl = oldTab.$el.getElementsByClassName('q-tab__indicator')[0],
            newEl = newTab.$el.getElementsByClassName('q-tab__indicator')[0];

          clearTimeout(this.animateTimer);

          oldEl.style.transition = 'none';
          oldEl.style.transform = 'none';
          newEl.style.transition = 'none';
          newEl.style.transform = 'none';

          var
            oldPos = oldEl.getBoundingClientRect(),
            newPos = newEl.getBoundingClientRect();

          newEl.style.transform = this.vertical === true
            ? ("translate3d(0," + (oldPos.top - newPos.top) + "px,0) scale3d(1," + (newPos.height ? oldPos.height / newPos.height : 1) + ",1)")
            : ("translate3d(" + (oldPos.left - newPos.left) + "px,0,0) scale3d(" + (newPos.width ? oldPos.width / newPos.width : 1) + ",1,1)");

          // allow scope updates to kick in
          this.$nextTick(function () {
            this$1.animateTimer = setTimeout(function () {
              newEl.style.transition = 'transform .25s cubic-bezier(.4, 0, .2, 1)';
              newEl.style.transform = 'none';
            }, 30);
          });
        }

        if (newTab && this.scrollable === true) {
          var ref = this.$refs.content.getBoundingClientRect();
          var left = ref.left;
          var width = ref.width;
          var top = ref.top;
          var height = ref.height;
          var newPos$1 = newTab.$el.getBoundingClientRect();

          var offset = this.vertical === true ? newPos$1.top - top : newPos$1.left - left;

          if (offset < 0) {
            this.$refs.content[this.vertical === true ? 'scrollTop' : 'scrollLeft'] += offset;
            this.__updateArrows();
            return
          }

          offset += this.vertical === true ? newPos$1.height - height : newPos$1.width - width;
          if (offset > 0) {
            this.$refs.content[this.vertical === true ? 'scrollTop' : 'scrollLeft'] += offset;
            this.__updateArrows();
          }
        }
      },

      __updateArrows: function __updateArrows () {
        var
          content = this.$refs.content,
          rect = content.getBoundingClientRect(),
          pos = this.vertical === true ? content.scrollTop : content.scrollLeft;

        this.leftArrow = pos > 0;
        this.rightArrow = this.vertical === true
          ? Math.ceil(pos + rect.height) < content.scrollHeight
          : Math.ceil(pos + rect.width) < content.scrollWidth;
      },

      __animScrollTo: function __animScrollTo (value) {
        var this$1 = this;

        this.__stopAnimScroll();
        this.__scrollTowards(value);

        this.scrollTimer = setInterval(function () {
          if (this$1.__scrollTowards(value)) {
            this$1.__stopAnimScroll();
          }
        }, 5);
      },

      __scrollToStart: function __scrollToStart () {
        this.__animScrollTo(0);
      },

      __scrollToEnd: function __scrollToEnd () {
        this.__animScrollTo(9999);
      },

      __stopAnimScroll: function __stopAnimScroll () {
        clearInterval(this.scrollTimer);
      },

      __scrollTowards: function __scrollTowards (value) {
        var
          content = this.$refs.content,
          pos = this.vertical === true ? content.scrollTop : content.scrollLeft,
          direction = value < pos ? -1 : 1,
          done = false;

        pos += direction * 5;
        if (pos < 0) {
          done = true;
          pos = 0;
        }
        else if (
          (direction === -1 && pos <= value) ||
          (direction === 1 && pos >= value)
        ) {
          done = true;
          pos = value;
        }

        content[this.vertical === true ? 'scrollTop' : 'scrollLeft'] = pos;
        this.__updateArrows();
        return done
      }
    },

    created: function created () {
      this.buffer = [];

      if (this.$q.platform.is.desktop !== true) {
        this.__updateArrows = noop;
      }
    },

    beforeDestroy: function beforeDestroy () {
      clearTimeout(this.bufferTimer);
      clearTimeout(this.animateTimer);
    },

    render: function render (h) {
      var child = [
        h(QResizeObserver, {
          on: cache(this, 'resize', { resize: this.__updateContainer })
        }),

        h('div', {
          ref: 'content',
          staticClass: 'q-tabs__content row no-wrap items-center self-stretch hide-scrollbar',
          class: this.alignClass
        }, slot(this, 'default'))
      ];

      this.$q.platform.is.desktop === true && child.push(
        h(QIcon, {
          staticClass: 'q-tabs__arrow q-tabs__arrow--left absolute q-tab__icon',
          class: this.leftArrow === true ? '' : 'q-tabs__arrow--faded',
          props: { name: this.leftIcon || (this.vertical === true ? this.$q.iconSet.tabs.up : this.$q.iconSet.tabs.left) },
          nativeOn: {
            mousedown: this.__scrollToStart,
            touchstart: this.__scrollToStart,
            mouseup: this.__stopAnimScroll,
            mouseleave: this.__stopAnimScroll,
            touchend: this.__stopAnimScroll
          }
        }),

        h(QIcon, {
          staticClass: 'q-tabs__arrow q-tabs__arrow--right absolute q-tab__icon',
          class: this.rightArrow === true ? '' : 'q-tabs__arrow--faded',
          props: { name: this.rightIcon || (this.vertical === true ? this.$q.iconSet.tabs.down : this.$q.iconSet.tabs.right) },
          nativeOn: {
            mousedown: this.__scrollToEnd,
            touchstart: this.__scrollToEnd,
            mouseup: this.__stopAnimScroll,
            mouseleave: this.__stopAnimScroll,
            touchend: this.__stopAnimScroll
          }
        })
      );

      return h('div', {
        staticClass: 'q-tabs row no-wrap items-center',
        class: this.classes,
        on: Object.assign({}, {input: stop},
          this.$listeners),
        attrs: { role: 'tablist' }
      }, child)
    }
  });

  var uid$1 = 0;

  var QTab = Vue.extend({
    name: 'QTab',

    mixins: [ RippleMixin ],

    inject: {
      tabs: {
        default: function default$1 () {
          console.error('QTab/QRouteTab components need to be child of QTabs');
        }
      },
      __activateTab: {},
      __recalculateScroll: {}
    },

    props: {
      icon: String,
      label: [Number, String],

      alert: [Boolean, String],

      name: {
        type: [Number, String],
        default: function () { return ("t_" + (uid$1++)); }
      },

      noCaps: Boolean,

      tabindex: [String, Number],
      disable: Boolean
    },

    computed: {
      isActive: function isActive () {
        return this.tabs.current === this.name
      },

      classes: function classes () {
        var obj;

        return ( obj = {}, obj[("q-tab--" + (this.isActive ? '' : 'in') + "active")] = true, obj[("text-" + (this.tabs.activeColor))] = this.isActive && this.tabs.activeColor, obj[("bg-" + (this.tabs.activeBgColor))] = this.isActive && this.tabs.activeBgColor, obj['q-tab--full'] = this.icon && this.label && !this.tabs.inlineLabel, obj['q-tab--no-caps'] = this.noCaps === true || this.tabs.noCaps === true, obj['q-focusable q-hoverable cursor-pointer'] = !this.disable, obj.disabled = this.disable, obj )
      },

      computedTabIndex: function computedTabIndex () {
        return this.disable === true || this.isActive === true ? -1 : this.tabindex || 0
      }
    },

    methods: {
      __activate: function __activate (e, keyboard) {
        keyboard !== true && this.$refs.blurTarget !== void 0 && this.$refs.blurTarget.focus();

        if (this.disable !== true) {
          this.$listeners.click !== void 0 && this.$emit('click', e);
          this.__activateTab(this.name);
        }
      },

      __onKeyup: function __onKeyup (e) {
        isKeyCode(e, 13) === true && this.__activate(e, true);
      },

      __getContent: function __getContent (h) {
        var
          narrow = this.tabs.narrowIndicator,
          content = [],
          indicator = h('div', {
            staticClass: 'q-tab__indicator',
            class: this.tabs.indicatorClass
          });

        this.icon !== void 0 && content.push(h(QIcon, {
          staticClass: 'q-tab__icon',
          props: { name: this.icon }
        }));

        this.label !== void 0 && content.push(h('div', {
          staticClass: 'q-tab__label'
        }, [ this.label ]));

        this.alert !== false && content.push(h('div', {
          staticClass: 'q-tab__alert',
          class: this.alert !== true ? ("text-" + (this.alert)) : null
        }));

        narrow && content.push(indicator);

        var node = [
          h('div', { staticClass: 'q-focus-helper', attrs: { tabindex: -1 }, ref: 'blurTarget' }),

          h('div', {
            staticClass: 'q-tab__content self-stretch flex-center relative-position q-anchor--skip non-selectable',
            class: this.tabs.inlineLabel === true ? 'row no-wrap q-tab__content--inline' : 'column'
          }, mergeSlot(content, this, 'default'))
        ];

        !narrow && node.push(indicator);

        return node
      },

      __renderTab: function __renderTab (h, tag, props) {
        var data = {
          staticClass: 'q-tab relative-position self-stretch flex flex-center text-center',
          class: this.classes,
          attrs: {
            tabindex: this.computedTabIndex,
            role: 'tab',
            'aria-selected': this.isActive
          },
          directives: this.ripple !== false && this.disable === true ? null : [
            { name: 'ripple', value: this.ripple }
          ]
        };
        data[tag === 'div' ? 'on' : 'nativeOn'] = Object.assign({}, {input: stop},
            this.$listeners,
            {click: this.__activate,
            keyup: this.__onKeyup});

        if (props !== void 0) {
          data.props = props;
        }

        return h(tag, data, this.__getContent(h))
      }
    },

    mounted: function mounted () {
      this.__recalculateScroll();
    },

    beforeDestroy: function beforeDestroy () {
      this.__recalculateScroll();
    },

    render: function render (h) {
      return this.__renderTab(h, 'div')
    }
  });

  var QTabPanels = Vue.extend({
    name: 'QTabPanels',

    mixins: [ DarkMixin, PanelParentMixin ],

    computed: {
      classes: function classes () {
        return 'q-tab-panels q-panel-parent' +
          (this.isDark === true ? ' q-tab-panels--dark q-dark' : '')
      }
    },

    methods: {
      __renderPanels: function __renderPanels (h) {
        return h('div', {
          class: this.classes,
          directives: this.panelDirectives,
          on: this.$listeners
        }, this.__getPanelContent(h))
      }
    }
  });

  var QTabPanel = Vue.extend({
    name: 'QTabPanel',

    mixins: [ PanelChildMixin ],

    render: function render (h) {
      return h('div', {
        staticClass: 'q-tab-panel',
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var palette = [
    'rgb(255,204,204)', 'rgb(255,230,204)', 'rgb(255,255,204)', 'rgb(204,255,204)', 'rgb(204,255,230)', 'rgb(204,255,255)', 'rgb(204,230,255)', 'rgb(204,204,255)', 'rgb(230,204,255)', 'rgb(255,204,255)',
    'rgb(255,153,153)', 'rgb(255,204,153)', 'rgb(255,255,153)', 'rgb(153,255,153)', 'rgb(153,255,204)', 'rgb(153,255,255)', 'rgb(153,204,255)', 'rgb(153,153,255)', 'rgb(204,153,255)', 'rgb(255,153,255)',
    'rgb(255,102,102)', 'rgb(255,179,102)', 'rgb(255,255,102)', 'rgb(102,255,102)', 'rgb(102,255,179)', 'rgb(102,255,255)', 'rgb(102,179,255)', 'rgb(102,102,255)', 'rgb(179,102,255)', 'rgb(255,102,255)',
    'rgb(255,51,51)', 'rgb(255,153,51)', 'rgb(255,255,51)', 'rgb(51,255,51)', 'rgb(51,255,153)', 'rgb(51,255,255)', 'rgb(51,153,255)', 'rgb(51,51,255)', 'rgb(153,51,255)', 'rgb(255,51,255)',
    'rgb(255,0,0)', 'rgb(255,128,0)', 'rgb(255,255,0)', 'rgb(0,255,0)', 'rgb(0,255,128)', 'rgb(0,255,255)', 'rgb(0,128,255)', 'rgb(0,0,255)', 'rgb(128,0,255)', 'rgb(255,0,255)',
    'rgb(245,0,0)', 'rgb(245,123,0)', 'rgb(245,245,0)', 'rgb(0,245,0)', 'rgb(0,245,123)', 'rgb(0,245,245)', 'rgb(0,123,245)', 'rgb(0,0,245)', 'rgb(123,0,245)', 'rgb(245,0,245)',
    'rgb(214,0,0)', 'rgb(214,108,0)', 'rgb(214,214,0)', 'rgb(0,214,0)', 'rgb(0,214,108)', 'rgb(0,214,214)', 'rgb(0,108,214)', 'rgb(0,0,214)', 'rgb(108,0,214)', 'rgb(214,0,214)',
    'rgb(163,0,0)', 'rgb(163,82,0)', 'rgb(163,163,0)', 'rgb(0,163,0)', 'rgb(0,163,82)', 'rgb(0,163,163)', 'rgb(0,82,163)', 'rgb(0,0,163)', 'rgb(82,0,163)', 'rgb(163,0,163)',
    'rgb(92,0,0)', 'rgb(92,46,0)', 'rgb(92,92,0)', 'rgb(0,92,0)', 'rgb(0,92,46)', 'rgb(0,92,92)', 'rgb(0,46,92)', 'rgb(0,0,92)', 'rgb(46,0,92)', 'rgb(92,0,92)',
    'rgb(255,255,255)', 'rgb(205,205,205)', 'rgb(178,178,178)', 'rgb(153,153,153)', 'rgb(127,127,127)', 'rgb(102,102,102)', 'rgb(76,76,76)', 'rgb(51,51,51)', 'rgb(25,25,25)', 'rgb(0,0,0)'
  ];

  var QColor = Vue.extend({
    name: 'QColor',

    mixins: [ DarkMixin, FormMixin ],

    directives: {
      TouchPan: TouchPan
    },

    props: {
      value: String,

      defaultValue: String,
      defaultView: {
        type: String,
        default: 'spectrum',
        validator: function (v) { return ['spectrum', 'tune', 'palette'].includes(v); }
      },

      formatModel: {
        type: String,
        default: 'auto',
        validator: function (v) { return ['auto', 'hex', 'rgb', 'hexa', 'rgba'].includes(v); }
      },

      palette: Array,

      noHeader: Boolean,
      noFooter: Boolean,

      square: Boolean,
      flat: Boolean,
      bordered: Boolean,

      disable: Boolean,
      readonly: Boolean
    },

    data: function data () {
      return {
        topView: this.formatModel === 'auto'
          ? (
            (this.value === void 0 || this.value === null || this.value === '' || this.value.startsWith('#'))
              ? 'hex'
              : 'rgb'
          )
          : (this.formatModel.startsWith('hex') ? 'hex' : 'rgb'),
        view: this.defaultView,
        model: this.__parseModel(this.value || this.defaultValue)
      }
    },

    watch: {
      value: function value (v) {
        var model = this.__parseModel(v || this.defaultValue);
        if (model.hex !== this.model.hex) {
          this.model = model;
        }
      },

      defaultValue: function defaultValue (v) {
        if (!this.value && v) {
          var model = this.__parseModel(v);
          if (model.hex !== this.model.hex) {
            this.model = model;
          }
        }
      }
    },

    computed: {
      editable: function editable () {
        return this.disable !== true && this.readonly !== true
      },

      forceHex: function forceHex () {
        return this.formatModel === 'auto'
          ? null
          : this.formatModel.indexOf('hex') > -1
      },

      forceAlpha: function forceAlpha () {
        return this.formatModel === 'auto'
          ? null
          : this.formatModel.indexOf('a') > -1
      },

      isHex: function isHex () {
        return this.value === void 0 ||
          this.value === null ||
          this.value === '' ||
          this.value.startsWith('#')
      },

      isOutputHex: function isOutputHex () {
        return this.forceHex !== null
          ? this.forceHex
          : this.isHex
      },

      formAttrs: function formAttrs () {
        return {
          type: 'hidden',
          name: this.name,
          value: this.model[ this.isOutputHex === true ? 'hex' : 'rgb' ]
        }
      },

      hasAlpha: function hasAlpha () {
        if (this.forceAlpha !== null) {
          return this.forceAlpha
        }
        return this.model.a !== void 0
      },

      currentBgColor: function currentBgColor () {
        return {
          backgroundColor: this.model.rgb || '#000'
        }
      },

      headerClass: function headerClass () {
        var light = this.model.a !== void 0 && this.model.a < 65
          ? true
          : luminosity(this.model) > 0.4;

        return ("q-color-picker__header-content--" + (light ? 'light' : 'dark'))
      },

      spectrumStyle: function spectrumStyle () {
        return {
          background: ("hsl(" + (this.model.h) + ",100%,50%)")
        }
      },

      spectrumPointerStyle: function spectrumPointerStyle () {
        var obj;

        return ( obj = {
          top: ((100 - this.model.v) + "%")
        }, obj[this.$q.lang.rtl === true ? 'right' : 'left'] = ((this.model.s) + "%"), obj )
      },

      inputsArray: function inputsArray () {
        var inp = ['r', 'g', 'b'];
        if (this.hasAlpha === true) {
          inp.push('a');
        }
        return inp
      },

      computedPalette: function computedPalette () {
        return this.palette !== void 0 && this.palette.length > 0
          ? this.palette
          : palette
      },

      classes: function classes () {
        return 'q-color-picker' +
          (this.bordered === true ? ' q-color-picker--bordered' : '') +
          (this.square === true ? ' q-color-picker--square no-border-radius' : '') +
          (this.flat === true ? ' q-color-picker--flat no-shadow' : '') +
          (this.disable === true ? ' disabled' : '') +
          (this.isDark === true ? ' q-color-picker--dark q-dark' : '')
      },

      attrs: function attrs () {
        if (this.disable === true) {
          return { 'aria-disabled': '' }
        }
        if (this.readonly === true) {
          return { 'aria-readonly': '' }
        }
      }
    },

    created: function created () {
      this.__spectrumChange = throttle(this.__spectrumChange, 20);
    },

    render: function render (h) {
      var child = [ this.__getContent(h) ];

      if (this.name !== void 0 && this.disable !== true) {
        this.__injectFormInput(child, 'push');
      }

      this.noHeader !== true && child.unshift(
        this.__getHeader(h)
      );

      this.noFooter !== true && child.push(
        this.__getFooter(h)
      );

      return h('div', {
        class: this.classes,
        attrs: this.attrs,
        on: this.$listeners
      }, child)
    },

    methods: {
      __getHeader: function __getHeader (h) {
        var this$1 = this;

        return h('div', {
          staticClass: 'q-color-picker__header relative-position overflow-hidden'
        }, [
          h('div', { staticClass: 'q-color-picker__header-bg absolute-full' }),

          h('div', {
            staticClass: 'q-color-picker__header-content absolute-full',
            class: this.headerClass,
            style: this.currentBgColor
          }, [
            h(QTabs, {
              props: {
                value: this.topView,
                dense: true,
                align: 'justify'
              },
              on: cache(this, 'topVTab', {
                input: function (val) { this$1.topView = val; }
              })
            }, [
              h(QTab, {
                props: {
                  label: 'HEX' + (this.hasAlpha === true ? 'A' : ''),
                  name: 'hex',
                  ripple: false
                }
              }),

              h(QTab, {
                props: {
                  label: 'RGB' + (this.hasAlpha === true ? 'A' : ''),
                  name: 'rgb',
                  ripple: false
                }
              })
            ]),

            h('div', {
              staticClass: 'q-color-picker__header-banner row flex-center no-wrap'
            }, [
              h('input', {
                staticClass: 'fit',
                domProps: { value: this.model[this.topView] },
                attrs: this.editable !== true ? {
                  readonly: true
                } : null,
                on: cache(this, 'topIn', {
                  input: function (evt) {
                    this$1.__updateErrorIcon(this$1.__onEditorChange(evt) === true);
                  },
                  change: stop,
                  blur: function (evt) {
                    this$1.__onEditorChange(evt, true) === true && this$1.$forceUpdate();
                    this$1.__updateErrorIcon(false);
                  }
                })
              }),

              h(QIcon, {
                ref: 'errorIcon',
                staticClass: 'q-color-picker__error-icon absolute no-pointer-events',
                props: { name: this.$q.iconSet.type.negative }
              })
            ])
          ])
        ])
      },

      __getContent: function __getContent (h) {
        return h(QTabPanels, {
          props: {
            value: this.view,
            animated: true
          }
        }, [
          h(QTabPanel, {
            staticClass: 'q-color-picker__spectrum-tab overflow-hidden',
            props: { name: 'spectrum' }
          }, this.__getSpectrumTab(h)),

          h(QTabPanel, {
            staticClass: 'q-pa-md q-color-picker__tune-tab',
            props: { name: 'tune' }
          }, this.__getTuneTab(h)),

          h(QTabPanel, {
            staticClass: 'q-color-picker__palette-tab',
            props: { name: 'palette' }
          }, this.__getPaletteTab(h))
        ])
      },

      __getFooter: function __getFooter (h) {
        var this$1 = this;

        return h('div', {
          staticClass: 'q-color-picker__footer relative-position overflow-hidden'
        }, [
          h(QTabs, {
            staticClass: 'absolute-full',
            props: {
              value: this.view,
              dense: true,
              align: 'justify'
            },
            on: cache(this, 'ftIn', {
              input: function (val) { this$1.view = val; }
            })
          }, [
            h(QTab, {
              props: {
                icon: this.$q.iconSet.colorPicker.spectrum,
                name: 'spectrum',
                ripple: false
              }
            }),

            h(QTab, {
              props: {
                icon: this.$q.iconSet.colorPicker.tune,
                name: 'tune',
                ripple: false
              }
            }),

            h(QTab, {
              props: {
                icon: this.$q.iconSet.colorPicker.palette,
                name: 'palette',
                ripple: false
              }
            })
          ])
        ])
      },

      __getSpectrumTab: function __getSpectrumTab (h) {
        var this$1 = this;

        var thumbPath = 'M5 5 h10 v10 h-10 v-10 z';

        return [
          h('div', {
            ref: 'spectrum',
            staticClass: 'q-color-picker__spectrum non-selectable relative-position cursor-pointer',
            style: this.spectrumStyle,
            class: { readonly: this.editable !== true },
            on: this.editable === true
              ? cache(this, 'spectrT', {
                click: this.__spectrumClick,
                mousedown: this.__activate
              })
              : null,
            directives: this.editable === true
              ? cache(this, 'spectrDir', [{
                name: 'touch-pan',
                modifiers: {
                  prevent: true,
                  stop: true,
                  mouse: true
                },
                value: this.__spectrumPan
              }])
              : null
          }, [
            h('div', { style: { paddingBottom: '100%' } }),
            h('div', { staticClass: 'q-color-picker__spectrum-white absolute-full' }),
            h('div', { staticClass: 'q-color-picker__spectrum-black absolute-full' }),
            h('div', {
              staticClass: 'absolute',
              style: this.spectrumPointerStyle
            }, [
              this.model.hex !== void 0 ? h('div', { staticClass: 'q-color-picker__spectrum-circle' }) : null
            ])
          ]),

          h('div', {
            staticClass: 'q-color-picker__sliders'
          }, [
            h('div', { staticClass: 'q-color-picker__hue non-selectable' }, [
              h(QSlider, {
                props: {
                  value: this.model.h,
                  min: 0,
                  max: 360,
                  fillHandleAlways: true,
                  readonly: this.editable !== true,
                  thumbPath: thumbPath
                },
                on: cache(this, 'hueSlide', {
                  input: this.__onHueChange,
                  change: function (val) { return this$1.__onHueChange(val, true); }
                })
              })
            ]),
            this.hasAlpha === true
              ? h('div', { staticClass: 'q-color-picker__alpha non-selectable' }, [
                h(QSlider, {
                  props: {
                    value: this.model.a,
                    min: 0,
                    max: 100,
                    fillHandleAlways: true,
                    readonly: this.editable !== true,
                    thumbPath: thumbPath
                  },
                  on: cache(this, 'alphaSlide', {
                    input: function (value) { return this$1.__onNumericChange(value, 'a', 100); },
                    change: function (value) { return this$1.__onNumericChange(value, 'a', 100, void 0, true); }
                  })
                })
              ])
              : null
          ])
        ]
      },

      __getTuneTab: function __getTuneTab (h) {
        var this$1 = this;

        return [
          h('div', { staticClass: 'row items-center no-wrap' }, [
            h('div', ['R']),
            h(QSlider, {
              props: {
                value: this.model.r,
                min: 0,
                max: 255,
                color: 'red',
                dark: this.isDark,
                readonly: this.editable !== true
              },
              on: cache(this, 'rSlide', {
                input: function (value) { return this$1.__onNumericChange(value, 'r', 255); },
                change: function (value) { return this$1.__onNumericChange(value, 'r', 255, void 0, true); }
              })
            }),
            h('input', {
              domProps: {
                value: this.model.r
              },
              attrs: {
                maxlength: 3,
                readonly: this.editable !== true
              },
              on: cache(this, 'rIn', {
                input: function (evt) { return this$1.__onNumericChange(evt.target.value, 'r', 255, evt); },
                change: stop,
                blur: function (evt) { return this$1.__onNumericChange(evt.target.value, 'r', 255, evt, true); }
              })
            })
          ]),

          h('div', { staticClass: 'row items-center no-wrap' }, [
            h('div', ['G']),
            h(QSlider, {
              props: {
                value: this.model.g,
                min: 0,
                max: 255,
                color: 'green',
                dark: this.isDark,
                readonly: this.editable !== true
              },
              on: cache(this, 'gSlide', {
                input: function (value) { return this$1.__onNumericChange(value, 'g', 255); },
                change: function (value) { return this$1.__onNumericChange(value, 'g', 255, void 0, true); }
              })
            }),
            h('input', {
              domProps: {
                value: this.model.g
              },
              attrs: {
                maxlength: 3,
                readonly: this.editable !== true
              },
              on: cache(this, 'gIn', {
                input: function (evt) { return this$1.__onNumericChange(evt.target.value, 'g', 255, evt); },
                change: stop,
                blur: function (evt) { return this$1.__onNumericChange(evt.target.value, 'g', 255, evt, true); }
              })
            })
          ]),

          h('div', { staticClass: 'row items-center no-wrap' }, [
            h('div', ['B']),
            h(QSlider, {
              props: {
                value: this.model.b,
                min: 0,
                max: 255,
                color: 'blue',
                readonly: this.editable !== true,
                dark: this.isDark
              },
              on: cache(this, 'bSlide', {
                input: function (value) { return this$1.__onNumericChange(value, 'b', 255); },
                change: function (value) { return this$1.__onNumericChange(value, 'b', 255, void 0, true); }
              })
            }),
            h('input', {
              domProps: {
                value: this.model.b
              },
              attrs: {
                maxlength: 3,
                readonly: this.editable !== true
              },
              on: cache(this, 'bIn', {
                input: function (evt) { return this$1.__onNumericChange(evt.target.value, 'b', 255, evt); },
                change: stop,
                blur: function (evt) { return this$1.__onNumericChange(evt.target.value, 'b', 255, evt, true); }
              })
            })
          ]),

          this.hasAlpha === true ? h('div', { staticClass: 'row items-center no-wrap' }, [
            h('div', ['A']),
            h(QSlider, {
              props: {
                value: this.model.a,
                color: 'grey',
                readonly: this.editable !== true,
                dark: this.isDark
              },
              on: cache(this, 'aSlide', {
                input: function (value) { return this$1.__onNumericChange(value, 'a', 100); },
                change: function (value) { return this$1.__onNumericChange(value, 'a', 100, void 0, true); }
              })
            }),
            h('input', {
              domProps: {
                value: this.model.a
              },
              attrs: {
                maxlength: 3,
                readonly: this.editable !== true
              },
              on: cache(this, 'aIn', {
                input: function (evt) { return this$1.__onNumericChange(evt.target.value, 'a', 100, evt); },
                change: stop,
                blur: function (evt) { return this$1.__onNumericChange(evt.target.value, 'a', 100, evt, true); }
              })
            })
          ]) : null
        ]
      },

      __getPaletteTab: function __getPaletteTab (h) {
        var this$1 = this;

        return [
          h('div', {
            staticClass: 'row items-center q-color-picker__palette-rows',
            class: this.editable === true
              ? 'q-color-picker__palette-rows--editable'
              : ''
          }, this.computedPalette.map(function (color) { return h('div', {
            staticClass: 'q-color-picker__cube col-auto',
            style: { backgroundColor: color },
            on: this$1.editable === true ? cache(this$1, 'palette#' + color, {
              click: function () {
                this$1.__onPalettePick(color);
              }
            }) : null
          }); }))
        ]
      },

      __onSpectrumChange: function __onSpectrumChange (left, top, change) {
        var panel = this.$refs.spectrum;
        if (panel === void 0) { return }

        var
          width = panel.clientWidth,
          height = panel.clientHeight,
          rect = panel.getBoundingClientRect();

        var x = Math.min(width, Math.max(0, left - rect.left));

        if (this.$q.lang.rtl === true) {
          x = width - x;
        }

        var
          y = Math.min(height, Math.max(0, top - rect.top)),
          s = Math.round(100 * x / width),
          v = Math.round(100 * Math.max(0, Math.min(1, -(y / height) + 1))),
          rgb = hsvToRgb({
            h: this.model.h,
            s: s,
            v: v,
            a: this.hasAlpha === true ? this.model.a : void 0
          });

        this.model.s = s;
        this.model.v = v;
        this.__update(rgb, change);
      },

      __onHueChange: function __onHueChange (h, change) {
        h = Math.round(h);
        var rgb = hsvToRgb({
          h: h,
          s: this.model.s,
          v: this.model.v,
          a: this.hasAlpha === true ? this.model.a : void 0
        });

        this.model.h = h;
        this.__update(rgb, change);
      },

      __onNumericChange: function __onNumericChange (value, formatModel, max, evt, change) {
        evt !== void 0 && stop(evt);

        if (!/^[0-9]+$/.test(value)) {
          change && this.$forceUpdate();
          return
        }

        var val = Math.floor(Number(value));

        if (val < 0 || val > max) {
          change === true && this.$forceUpdate();
          return
        }

        var rgb = {
          r: formatModel === 'r' ? val : this.model.r,
          g: formatModel === 'g' ? val : this.model.g,
          b: formatModel === 'b' ? val : this.model.b,
          a: this.hasAlpha === true
            ? (formatModel === 'a' ? val : this.model.a)
            : void 0
        };

        if (formatModel !== 'a') {
          var hsv = rgbToHsv(rgb);
          this.model.h = hsv.h;
          this.model.s = hsv.s;
          this.model.v = hsv.v;
        }

        this.__update(rgb, change);

        if (evt !== void 0 && change !== true && evt.target.selectionEnd !== void 0) {
          var index = evt.target.selectionEnd;
          this.$nextTick(function () {
            evt.target.setSelectionRange(index, index);
          });
        }
      },

      __onEditorChange: function __onEditorChange (evt, change) {
        var rgb;
        var inp = evt.target.value;

        stop(evt);

        if (this.topView === 'hex') {
          if (
            inp.length !== (this.hasAlpha === true ? 9 : 7) ||
            !/^#[0-9A-Fa-f]+$/.test(inp)
          ) {
            return true
          }

          rgb = hexToRgb(inp);
        }
        else {
          var model;

          if (!inp.endsWith(')')) {
            return true
          }
          else if (this.hasAlpha !== true && inp.startsWith('rgb(')) {
            model = inp.substring(4, inp.length - 1).split(',').map(function (n) { return parseInt(n, 10); });

            if (
              model.length !== 3 ||
              !/^rgb\([0-9]{1,3},[0-9]{1,3},[0-9]{1,3}\)$/.test(inp)
            ) {
              return true
            }
          }
          else if (this.hasAlpha === true && inp.startsWith('rgba(')) {
            model = inp.substring(5, inp.length - 1).split(',');

            if (
              model.length !== 4 ||
              !/^rgba\([0-9]{1,3},[0-9]{1,3},[0-9]{1,3},(0|0\.[0-9]+[1-9]|0\.[1-9]+|1)\)$/.test(inp)
            ) {
              return true
            }

            for (var i = 0; i < 3; i++) {
              var v = parseInt(model[i], 10);
              if (v < 0 || v > 255) {
                return true
              }
              model[i] = v;
            }

            var v$1 = parseFloat(model[3]);
            if (v$1 < 0 || v$1 > 1) {
              return true
            }
            model[3] = v$1;
          }
          else {
            return true
          }

          if (
            model[0] < 0 || model[0] > 255 ||
            model[1] < 0 || model[1] > 255 ||
            model[2] < 0 || model[2] > 255 ||
            (this.hasAlpha === true && (model[3] < 0 || model[3] > 1))
          ) {
            return true
          }

          rgb = {
            r: model[0],
            g: model[1],
            b: model[2],
            a: this.hasAlpha === true
              ? model[3] * 100
              : void 0
          };
        }

        var hsv = rgbToHsv(rgb);
        this.model.h = hsv.h;
        this.model.s = hsv.s;
        this.model.v = hsv.v;

        this.__update(rgb, change);

        if (change !== true) {
          var index = evt.target.selectionEnd;
          this.$nextTick(function () {
            evt.target.setSelectionRange(index, index);
          });
        }
      },

      __onPalettePick: function __onPalettePick (color) {
        var def = this.__parseModel(color);
        var rgb = { r: def.r, g: def.g, b: def.b, a: def.a };

        if (rgb.a === void 0) {
          rgb.a = this.model.a;
        }

        this.model.h = def.h;
        this.model.s = def.s;
        this.model.v = def.v;

        this.__update(rgb, true);
      },

      __update: function __update (rgb, change) {
        // update internally
        this.model.hex = rgbToHex(rgb);
        this.model.rgb = rgbToString(rgb);
        this.model.r = rgb.r;
        this.model.g = rgb.g;
        this.model.b = rgb.b;
        this.model.a = rgb.a;

        var value = this.model[this.isOutputHex === true ? 'hex' : 'rgb'];

        // emit new value
        this.$emit('input', value);
        change === true && this.$emit('change', value);
      },

      __updateErrorIcon: function __updateErrorIcon (val) {
        // we MUST avoid vue triggering a render,
        // so manually changing this
        if (this.$refs.errorIcon !== void 0) {
          this.$refs.errorIcon.$el.style.opacity = val ? 1 : 0;
        }
      },

      __parseModel: function __parseModel (v) {
        var forceAlpha = this.forceAlpha !== void 0
          ? this.forceAlpha
          : (
            this.formatModel === 'auto'
              ? null
              : this.formatModel.indexOf('a') > -1
          );

        if (v === null || v === void 0 || v === '' || testPattern.anyColor(v) !== true) {
          return {
            h: 0,
            s: 0,
            v: 0,
            r: 0,
            g: 0,
            b: 0,
            a: forceAlpha === true ? 100 : void 0,
            hex: void 0,
            rgb: void 0
          }
        }

        var model = stringToRgb(v);

        if (forceAlpha === true && model.a === void 0) {
          model.a = 100;
        }

        model.hex = rgbToHex(model);
        model.rgb = rgbToString(model);

        return Object.assign(model, rgbToHsv(model))
      },

      __spectrumPan: function __spectrumPan (evt) {
        if (evt.isFinal) {
          this.__onSpectrumChange(
            evt.position.left,
            evt.position.top,
            true
          );
        }
        else {
          this.__spectrumChange(evt);
        }
      },

      // throttled in created()
      __spectrumChange: function __spectrumChange (evt) {
        this.__onSpectrumChange(
          evt.position.left,
          evt.position.top
        );
      },

      __spectrumClick: function __spectrumClick (evt) {
        this.__onSpectrumChange(
          evt.pageX - window.pageXOffset,
          evt.pageY - window.pageYOffset,
          true
        );
      },

      __activate: function __activate (evt) {
        this.__onSpectrumChange(
          evt.pageX - window.pageXOffset,
          evt.pageY - window.pageYOffset
        );
      }
    }
  });

  // taken from https://github.com/jalaali/jalaali-js

  /*
    Jalaali years starting the 33-year rule.
  */
  var breaks = [ -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178
  ];

  /*
    Converts a Gregorian date to Jalaali.
  */
  function toJalaali (gy, gm, gd) {
    if (Object.prototype.toString.call(gy) === '[object Date]') {
      gd = gy.getDate();
      gm = gy.getMonth() + 1;
      gy = gy.getFullYear();
    }
    return d2j(g2d(gy, gm, gd))
  }

  /*
    Converts a Jalaali date to Gregorian.
  */
  function toGregorian (jy, jm, jd) {
    return d2g(j2d(jy, jm, jd))
  }

  /*
    Is this a leap year or not?
  */
  function isLeapJalaaliYear (jy) {
    return jalCalLeap(jy) === 0
  }

  /*
    Number of days in a given month in a Jalaali year.
  */
  function jalaaliMonthLength (jy, jm) {
    if (jm <= 6) { return 31 }
    if (jm <= 11) { return 30 }
    if (isLeapJalaaliYear(jy)) { return 30 }
    return 29
  }

  /*
      This function determines if the Jalaali (Persian) year is
      leap (366-day long) or is the common year (365 days)

      @param jy Jalaali calendar year (-61 to 3177)
      @returns number of years since the last leap year (0 to 4)
   */
  function jalCalLeap (jy) {
    var bl = breaks.length,
      jp = breaks[0],
      jm,
      jump,
      leap,
      n,
      i;

    if (jy < jp || jy >= breaks[bl - 1]) { throw new Error('Invalid Jalaali year ' + jy) }

    for (i = 1; i < bl; i += 1) {
      jm = breaks[i];
      jump = jm - jp;
      if (jy < jm) { break }
      jp = jm;
    }
    n = jy - jp;

    if (jump - n < 6) { n = n - jump + div(jump + 4, 33) * 33; }
    leap = mod(mod(n + 1, 33) - 1, 4);
    if (leap === -1) {
      leap = 4;
    }

    return leap
  }

  /*
    This function determines if the Jalaali (Persian) year is
    leap (366-day long) or is the common year (365 days), and
    finds the day in March (Gregorian calendar) of the first
    day of the Jalaali year (jy).

    @param jy Jalaali calendar year (-61 to 3177)
    @param withoutLeap when don't need leap (true or false) default is false
    @return
      leap: number of years since the last leap year (0 to 4)
      gy: Gregorian year of the beginning of Jalaali year
      march: the March day of Farvardin the 1st (1st day of jy)
    @see: http://www.astro.uni.torun.pl/~kb/Papers/EMP/PersianC-EMP.htm
    @see: http://www.fourmilab.ch/documents/calendar/
  */
  function jalCal (jy, withoutLeap) {
    var bl = breaks.length,
      gy = jy + 621,
      leapJ = -14,
      jp = breaks[0],
      jm,
      jump,
      leap,
      leapG,
      march,
      n,
      i;

    if (jy < jp || jy >= breaks[bl - 1]) { throw new Error('Invalid Jalaali year ' + jy) }

    // Find the limiting years for the Jalaali year jy.
    for (i = 1; i < bl; i += 1) {
      jm = breaks[i];
      jump = jm - jp;
      if (jy < jm) { break }
      leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
      jp = jm;
    }
    n = jy - jp;

    // Find the number of leap years from AD 621 to the beginning
    // of the current Jalaali year in the Persian calendar.
    leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
    if (mod(jump, 33) === 4 && jump - n === 4) { leapJ += 1; }

    // And the same in the Gregorian calendar (until the year gy).
    leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;

    // Determine the Gregorian date of Farvardin the 1st.
    march = 20 + leapJ - leapG;

    // Find how many years have passed since the last leap year.
    if (!withoutLeap) {
      if (jump - n < 6) { n = n - jump + div(jump + 4, 33) * 33; }
      leap = mod(mod(n + 1, 33) - 1, 4);
      if (leap === -1) {
        leap = 4;
      }
    }

    return {
      leap: leap,
      gy: gy,
      march: march
    }
  }

  /*
    Converts a date of the Jalaali calendar to the Julian Day number.

    @param jy Jalaali year (1 to 3100)
    @param jm Jalaali month (1 to 12)
    @param jd Jalaali day (1 to 29/31)
    @return Julian Day number
  */
  function j2d (jy, jm, jd) {
    var r = jalCal(jy, true);
    return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1
  }

  /*
    Converts the Julian Day number to a date in the Jalaali calendar.

    @param jdn Julian Day number
    @return
      jy: Jalaali year (1 to 3100)
      jm: Jalaali month (1 to 12)
      jd: Jalaali day (1 to 29/31)
  */
  function d2j (jdn) {
    var gy = d2g(jdn).gy, // Calculate Gregorian year (gy).
      jy = gy - 621,
      r = jalCal(jy, false),
      jdn1f = g2d(gy, 3, r.march),
      jd,
      jm,
      k;

    // Find number of days that passed since 1 Farvardin.
    k = jdn - jdn1f;
    if (k >= 0) {
      if (k <= 185) {
        // The first 6 months.
        jm = 1 + div(k, 31);
        jd = mod(k, 31) + 1;
        return { jy: jy,
          jm: jm,
          jd: jd
        }
      }
      else {
        // The remaining months.
        k -= 186;
      }
    }
    else {
      // Previous Jalaali year.
      jy -= 1;
      k += 179;
      if (r.leap === 1) { k += 1; }
    }
    jm = 7 + div(k, 30);
    jd = mod(k, 30) + 1;
    return { jy: jy,
      jm: jm,
      jd: jd
    }
  }

  /*
    Calculates the Julian Day number from Gregorian or Julian
    calendar dates. This integer number corresponds to the noon of
    the date (i.e. 12 hours of Universal Time).
    The procedure was tested to be good since 1 March, -100100 (of both
    calendars) up to a few million years into the future.

    @param gy Calendar year (years BC numbered 0, -1, -2, ...)
    @param gm Calendar month (1 to 12)
    @param gd Calendar day of the month (1 to 28/29/30/31)
    @return Julian Day number
  */
  function g2d (gy, gm, gd) {
    var d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4) +
        div(153 * mod(gm + 9, 12) + 2, 5) +
        gd - 34840408;
    d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
    return d
  }

  /*
    Calculates Gregorian and Julian calendar dates from the Julian Day number
    (jdn) for the period since jdn=-34839655 (i.e. the year -100100 of both
    calendars) to some millions years ahead of the present.

    @param jdn Julian Day number
    @return
      gy: Calendar year (years BC numbered 0, -1, -2, ...)
      gm: Calendar month (1 to 12)
      gd: Calendar day of the month M (1 to 28/29/30/31)
  */
  function d2g (jdn) {
    var j,
      i,
      gd,
      gm,
      gy;
    j = 4 * jdn + 139361631;
    j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
    i = div(mod(j, 1461), 4) * 5 + 308;
    gd = div(mod(i, 153), 5) + 1;
    gm = mod(div(i, 153), 12) + 1;
    gy = div(j, 1461) - 100100 + div(8 - gm, 6);
    return {
      gy: gy,
      gm: gm,
      gd: gd
    }
  }

  /*
    Utility helper functions.
  */

  function div (a, b) {
    return ~~(a / b)
  }

  function mod (a, b) {
    return a - ~~(a / b) * b
  }

  var DateTimeMixin = {
    mixins: [ DarkMixin, FormMixin ],

    props: {
      value: {
        required: true
      },

      mask: {
        type: String
      },
      locale: Object,

      calendar: {
        type: String,
        validator: function (v) { return ['gregorian', 'persian'].includes(v); },
        default: 'gregorian'
      },

      landscape: Boolean,

      color: String,
      textColor: String,

      square: Boolean,
      flat: Boolean,
      bordered: Boolean,

      readonly: Boolean,
      disable: Boolean
    },

    watch: {
      mask: function mask () {
        var this$1 = this;

        this.$nextTick(function () {
          this$1.__updateValue({}, /* reason for QDate only */ 'mask');
        });
      },

      computedLocale: function computedLocale () {
        var this$1 = this;

        this.$nextTick(function () {
          this$1.__updateValue({}, /* reason for QDate only */ 'locale');
        });
      }
    },

    computed: {
      editable: function editable () {
        return this.disable !== true && this.readonly !== true
      },

      computedColor: function computedColor () {
        return this.color || 'primary'
      },

      computedTextColor: function computedTextColor () {
        return this.textColor || 'white'
      },

      computedTabindex: function computedTabindex () {
        return this.editable === true ? 0 : -1
      },

      headerClass: function headerClass () {
        var cls = [];
        this.color !== void 0 && cls.push(("bg-" + (this.color)));
        this.textColor !== void 0 && cls.push(("text-" + (this.textColor)));
        return cls.join(' ')
      },

      computedLocale: function computedLocale () {
        return this.__getComputedLocale()
      }
    },

    methods: {
      __getComputedLocale: function __getComputedLocale () {
        return this.locale || this.$q.lang.date
      },

      __getCurrentDate: function __getCurrentDate () {
        var d = new Date();

        if (this.calendar === 'persian') {
          var jDate = toJalaali(d);
          return {
            year: jDate.jy,
            month: jDate.jm,
            day: jDate.jd
          }
        }

        return {
          year: d.getFullYear(),
          month: d.getMonth() + 1,
          day: d.getDate()
        }
      },

      __getCurrentTime: function __getCurrentTime () {
        var d = new Date();

        return {
          hour: d.getHours(),
          minute: d.getMinutes(),
          second: d.getSeconds(),
          millisecond: d.getMilliseconds()
        }
      }
    }
  };

  /* eslint no-fallthrough: 0 */

  var
    MILLISECONDS_IN_DAY = 86400000,
    MILLISECONDS_IN_HOUR = 3600000,
    MILLISECONDS_IN_MINUTE = 60000,
    defaultMask = 'YYYY-MM-DDTHH:mm:ss.SSSZ',
    token = /\[((?:[^\]\\]|\\]|\\)*)\]|d{1,4}|M{1,4}|m{1,2}|w{1,2}|Qo|Do|D{1,4}|YY(?:YY)?|H{1,2}|h{1,2}|s{1,2}|S{1,3}|Z{1,2}|a{1,2}|[AQExX]/g,
    reverseToken = /(\[[^\]]*\])|d{1,4}|M{1,4}|m{1,2}|w{1,2}|Qo|Do|D{1,4}|YY(?:YY)?|H{1,2}|h{1,2}|s{1,2}|S{1,3}|Z{1,2}|a{1,2}|[AQExX]|([.*+:?^,\s${}()|\\]+)/g,
    regexStore = {};

  function getRegexData (mask, dateLocale) {
    var
      days = '(' + dateLocale.days.join('|') + ')',
      key = mask + days;

    if (regexStore[key] !== void 0) {
      return regexStore[key]
    }

    var
      daysShort = '(' + dateLocale.daysShort.join('|') + ')',
      months = '(' + dateLocale.months.join('|') + ')',
      monthsShort = '(' + dateLocale.monthsShort.join('|') + ')';

    var map = {};
    var index = 0;

    var regexText = mask.replace(reverseToken, function (match) {
      index++;
      switch (match) {
        case 'YY':
          map.YY = index;
          return '(-?\\d{1,2})'
        case 'YYYY':
          map.YYYY = index;
          return '(-?\\d{1,4})'
        case 'M':
          map.M = index;
          return '(\\d{1,2})'
        case 'MM':
          map.M = index; // bumping to M
          return '(\\d{2})'
        case 'MMM':
          map.MMM = index;
          return monthsShort
        case 'MMMM':
          map.MMMM = index;
          return months
        case 'D':
          map.D = index;
          return '(\\d{1,2})'
        case 'Do':
          map.D = index++; // bumping to D
          return '(\\d{1,2}(st|nd|rd|th))'
        case 'DD':
          map.D = index; // bumping to D
          return '(\\d{2})'
        case 'H':
          map.H = index;
          return '(\\d{1,2})'
        case 'HH':
          map.H = index; // bumping to H
          return '(\\d{2})'
        case 'h':
          map.h = index;
          return '(\\d{1,2})'
        case 'hh':
          map.h = index; // bumping to h
          return '(\\d{2})'
        case 'm':
          map.m = index;
          return '(\\d{1,2})'
        case 'mm':
          map.m = index; // bumping to m
          return '(\\d{2})'
        case 's':
          map.s = index;
          return '(\\d{1,2})'
        case 'ss':
          map.s = index; // bumping to s
          return '(\\d{2})'
        case 'S':
          map.S = index;
          return '(\\d{1})'
        case 'SS':
          map.S = index; // bump to S
          return '(\\d{2})'
        case 'SSS':
          map.S = index; // bump to S
          return '(\\d{3})'
        case 'A':
          map.A = index;
          return '(AM|PM)'
        case 'a':
          map.a = index;
          return '(am|pm)'
        case 'aa':
          map.aa = index;
          return '(a\\.m\\.|p\\.m\\.)'

        case 'ddd':
          return daysShort
        case 'dddd':
          return days
        case 'Q':
        case 'd':
        case 'E':
          return '(\\d{1})'
        case 'Qo':
          return '(1st|2nd|3rd|4th)'
        case 'DDD':
        case 'DDDD':
          return '(\\d{1,3})'
        case 'w':
          return '(\\d{1,2})'
        case 'ww':
          return '(\\d{2})'

        case 'Z': // to split: (?:(Z)()()|([+-])?(\\d{2}):?(\\d{2}))
          return '(Z|[+-]\\d{2}:\\d{2})'
        case 'ZZ':
          return '(Z|[+-]\\d{2}\\d{2})'

        case 'X':
          map.X = index;
          return '(-?\\d+)'
        case 'x':
          map.x = index;
          return '(-?\\d{4,})'

        default:
          index--;
          if (match[0] === '[') {
            match = match.substring(1, match.length - 1);
          }
          return match.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      }
    });

    var res = { map: map, regex: new RegExp('^' + regexText) };
    regexStore[key] = res;

    return res
  }

  function extractDate (str, mask, dateLocale) {
    var d = __splitDate(str, mask, dateLocale);

    return new Date(
      d.year,
      d.month === null ? null : d.month - 1,
      d.day,
      d.hour,
      d.minute,
      d.second,
      d.millisecond
    )
  }

  function __splitDate (str, mask, dateLocale, calendar, defaultModel) {
    var date = Object.assign({
      year: null,
      month: null,
      day: null,
      hour: null,
      minute: null,
      second: null,
      millisecond: null,
      dateHash: null,
      timeHash: null
    }, defaultModel);

    if (
      str === void 0 ||
      str === null ||
      str === '' ||
      typeof str !== 'string'
    ) {
      return date
    }

    if (mask === void 0) {
      mask = defaultMask;
    }

    var
      langOpts = dateLocale !== void 0 ? dateLocale : lang.props.date,
      months = langOpts.months,
      monthsShort = langOpts.monthsShort;

    var ref = getRegexData(mask, langOpts);
    var regex = ref.regex;
    var map = ref.map;

    var match = str.match(regex);

    if (match === null) {
      return date
    }

    if (map.X !== void 0 || map.x !== void 0) {
      var stamp = parseInt(match[map.X !== void 0 ? map.X : map.x], 10);

      if (isNaN(stamp) === true || stamp < 0) {
        return date
      }

      var d = new Date(stamp * (map.X !== void 0 ? 1000 : 1));

      date.year = d.getFullYear();
      date.month = d.getMonth() + 1;
      date.day = d.getDate();
      date.hour = d.getHours();
      date.minute = d.getMinutes();
      date.second = d.getSeconds();
      date.millisecond = d.getMilliseconds();
    }
    else {
      if (map.YYYY !== void 0) {
        date.year = parseInt(match[map.YYYY], 10);
      }
      else if (map.YY !== void 0) {
        var y = parseInt(match[map.YY], 10);
        date.year = y < 0 ? y : 2000 + y;
      }

      if (map.M !== void 0) {
        date.month = parseInt(match[map.M], 10);
        if (date.month < 1 || date.month > 12) {
          return date
        }
      }
      else if (map.MMM !== void 0) {
        date.month = monthsShort.indexOf(match[map.MMM]) + 1;
      }
      else if (map.MMMM !== void 0) {
        date.month = months.indexOf(match[map.MMMM]) + 1;
      }

      if (map.D !== void 0) {
        date.day = parseInt(match[map.D], 10);

        if (date.year === null || date.month === null || date.day < 1) {
          return date
        }

        var maxDay = calendar !== 'persian'
          ? (new Date(date.year, date.month, 0)).getDate()
          : jalaaliMonthLength(date.year, date.month);

        if (date.day > maxDay) {
          return date
        }
      }

      if (map.H !== void 0) {
        date.hour = parseInt(match[map.H], 10) % 24;
      }
      else if (map.h !== void 0) {
        date.hour = parseInt(match[map.h], 10) % 12;
        if (
          (map.A && match[map.A] === 'PM') ||
          (map.a && match[map.a] === 'pm') ||
          (map.aa && match[map.aa] === 'p.m.')
        ) {
          date.hour += 12;
        }
        date.hour = date.hour % 24;
      }

      if (map.m !== void 0) {
        date.minute = parseInt(match[map.m], 10) % 60;
      }

      if (map.s !== void 0) {
        date.second = parseInt(match[map.s], 10) % 60;
      }

      if (map.S !== void 0) {
        date.millisecond = parseInt(match[map.S], 10) * Math.pow( 10, (3 - match[map.S].length) );
      }
    }

    date.dateHash = date.year + '/' + pad(date.month) + '/' + pad(date.day);
    date.timeHash = pad(date.hour) + ':' + pad(date.minute) + ':' + pad(date.second);

    return date
  }

  function formatTimezone (offset, delimeter) {
    if ( delimeter === void 0 ) delimeter = '';

    var
      sign = offset > 0 ? '-' : '+',
      absOffset = Math.abs(offset),
      hours = Math.floor(absOffset / 60),
      minutes = absOffset % 60;

    return sign + pad(hours) + delimeter + pad(minutes)
  }

  function setMonth (date, newMonth /* 1-based */) {
    var
      test = new Date(date.getFullYear(), newMonth, 0, 0, 0, 0, 0),
      days = test.getDate();

    date.setMonth(newMonth - 1, Math.min(days, date.getDate()));
  }

  function getChange (date, mod, add) {
    var
      t = new Date(date),
      sign = (add ? 1 : -1);

    Object.keys(mod).forEach(function (key) {
      if (key === 'month') {
        setMonth(t, t.getMonth() + 1 + sign * mod.month);
        return
      }

      var op = key === 'year'
        ? 'FullYear'
        : capitalize(key === 'days' ? 'date' : key);
      t[("set" + op)](t[("get" + op)]() + sign * mod[key]);
    });
    return t
  }

  function isValid (date) {
    return typeof date === 'number'
      ? true
      : isNaN(Date.parse(date)) === false
  }

  function buildDate (mod, utc) {
    return adjustDate(new Date(), mod, utc)
  }

  function getDayOfWeek (date) {
    var dow = new Date(date).getDay();
    return dow === 0 ? 7 : dow
  }

  function getWeekOfYear (date) {
    // Remove time components of date
    var thursday = new Date(date.getFullYear(), date.getMonth(), date.getDate());

    // Change date to Thursday same week
    thursday.setDate(thursday.getDate() - ((thursday.getDay() + 6) % 7) + 3);

    // Take January 4th as it is always in week 1 (see ISO 8601)
    var firstThursday = new Date(thursday.getFullYear(), 0, 4);

    // Change date to Thursday same week
    firstThursday.setDate(firstThursday.getDate() - ((firstThursday.getDay() + 6) % 7) + 3);

    // Check if daylight-saving-time-switch occurred and correct for it
    var ds = thursday.getTimezoneOffset() - firstThursday.getTimezoneOffset();
    thursday.setHours(thursday.getHours() - ds);

    // Number of weeks between target Thursday and first Thursday
    var weekDiff = (thursday - firstThursday) / (MILLISECONDS_IN_DAY * 7);
    return 1 + Math.floor(weekDiff)
  }

  function isBetweenDates (date, from, to, opts) {
    if ( opts === void 0 ) opts = {};

    var
      d1 = new Date(from).getTime(),
      d2 = new Date(to).getTime(),
      cur = new Date(date).getTime();

    opts.inclusiveFrom && d1--;
    opts.inclusiveTo && d2++;

    return cur > d1 && cur < d2
  }

  function addToDate (date, mod) {
    return getChange(date, mod, true)
  }
  function subtractFromDate (date, mod) {
    return getChange(date, mod, false)
  }

  function adjustDate (date, mod, utc) {
    var
      t = new Date(date),
      prefix = "set" + (utc ? 'UTC' : '');

    Object.keys(mod).forEach(function (key) {
      if (key === 'month') {
        setMonth(t, mod.month);
        return
      }

      var op = key === 'year'
        ? 'FullYear'
        : key.charAt(0).toUpperCase() + key.slice(1);
      t[("" + prefix + op)](mod[key]);
    });

    return t
  }

  function startOfDate (date, unit) {
    var t = new Date(date);
    switch (unit) {
      case 'year':
        t.setMonth(0);
      case 'month':
        t.setDate(1);
      case 'day':
        t.setHours(0);
      case 'hour':
        t.setMinutes(0);
      case 'minute':
        t.setSeconds(0);
      case 'second':
        t.setMilliseconds(0);
    }
    return t
  }

  function endOfDate (date, unit) {
    var t = new Date(date);
    switch (unit) {
      case 'year':
        t.setMonth(11);
      case 'month':
        t.setDate(daysInMonth(t));
      case 'day':
        t.setHours(23);
      case 'hour':
        t.setMinutes(59);
      case 'minute':
        t.setSeconds(59);
      case 'second':
        t.setMilliseconds(59);
    }
    return t
  }

  function getMaxDate (/* date, ...args */) {
    var t = 0;
    Array.prototype.slice.call(arguments).forEach(function (d) {
      t = Math.max(t, new Date(d));
    });
    return t
  }

  function getMinDate (date /*, ...args */) {
    var t = new Date(date);
    Array.prototype.slice.call(arguments, 1).forEach(function (d) {
      t = Math.min(t, new Date(d));
    });
    return t
  }

  function getDiff (t, sub, interval) {
    return (
      (t.getTime() - t.getTimezoneOffset() * MILLISECONDS_IN_MINUTE) -
      (sub.getTime() - sub.getTimezoneOffset() * MILLISECONDS_IN_MINUTE)
    ) / interval
  }

  function getDateDiff (date, subtract, unit) {
    if ( unit === void 0 ) unit = 'days';

    var
      t = new Date(date),
      sub = new Date(subtract);

    switch (unit) {
      case 'years':
        return (t.getFullYear() - sub.getFullYear())

      case 'months':
        return (t.getFullYear() - sub.getFullYear()) * 12 + t.getMonth() - sub.getMonth()

      case 'days':
        return getDiff(startOfDate(t, 'day'), startOfDate(sub, 'day'), MILLISECONDS_IN_DAY)

      case 'hours':
        return getDiff(startOfDate(t, 'hour'), startOfDate(sub, 'hour'), MILLISECONDS_IN_HOUR)

      case 'minutes':
        return getDiff(startOfDate(t, 'minute'), startOfDate(sub, 'minute'), MILLISECONDS_IN_MINUTE)

      case 'seconds':
        return getDiff(startOfDate(t, 'second'), startOfDate(sub, 'second'), 1000)
    }
  }

  function getDayOfYear (date) {
    return getDateDiff(date, startOfDate(date, 'year'), 'days') + 1
  }

  function inferDateFormat (date) {
    return isDate(date) === true
      ? 'date'
      : (typeof date === 'number' ? 'number' : 'string')
  }

  function getDateBetween (date, min, max) {
    var t = new Date(date);

    if (min) {
      var low = new Date(min);
      if (t < low) {
        return low
      }
    }

    if (max) {
      var high = new Date(max);
      if (t > high) {
        return high
      }
    }

    return t
  }

  function isSameDate (date, date2, unit) {
    var
      t = new Date(date),
      d = new Date(date2);

    if (unit === void 0) {
      return t.getTime() === d.getTime()
    }

    switch (unit) {
      case 'second':
        if (t.getSeconds() !== d.getSeconds()) {
          return false
        }
      case 'minute': // intentional fall-through
        if (t.getMinutes() !== d.getMinutes()) {
          return false
        }
      case 'hour': // intentional fall-through
        if (t.getHours() !== d.getHours()) {
          return false
        }
      case 'day': // intentional fall-through
        if (t.getDate() !== d.getDate()) {
          return false
        }
      case 'month': // intentional fall-through
        if (t.getMonth() !== d.getMonth()) {
          return false
        }
      case 'year': // intentional fall-through
        if (t.getFullYear() !== d.getFullYear()) {
          return false
        }
        break
      default:
        throw new Error(("date isSameDate unknown unit " + unit))
    }

    return true
  }

  function daysInMonth (date) {
    return (new Date(date.getFullYear(), date.getMonth() + 1, 0)).getDate()
  }

  function getOrdinal (n) {
    if (n >= 11 && n <= 13) {
      return (n + "th")
    }
    switch (n % 10) {
      case 1: return (n + "st")
      case 2: return (n + "nd")
      case 3: return (n + "rd")
    }
    return (n + "th")
  }

  var formatter = {
    // Year: 00, 01, ..., 99
    YY: function YY (date, _, forcedYear) {
      // workaround for < 1900 with new Date()
      var y = this.YYYY(date, _, forcedYear) % 100;
      return y > 0
        ? pad(y)
        : '-' + pad(Math.abs(y))
    },

    // Year: 1900, 1901, ..., 2099
    YYYY: function YYYY (date, _, forcedYear) {
      // workaround for < 1900 with new Date()
      return forcedYear !== void 0 && forcedYear !== null
        ? forcedYear
        : date.getFullYear()
    },

    // Month: 1, 2, ..., 12
    M: function M (date) {
      return date.getMonth() + 1
    },

    // Month: 01, 02, ..., 12
    MM: function MM (date) {
      return pad(date.getMonth() + 1)
    },

    // Month Short Name: Jan, Feb, ...
    MMM: function MMM (date, dateLocale) {
      return dateLocale.monthsShort[date.getMonth()]
    },

    // Month Name: January, February, ...
    MMMM: function MMMM (date, dateLocale) {
      return dateLocale.months[date.getMonth()]
    },

    // Quarter: 1, 2, 3, 4
    Q: function Q (date) {
      return Math.ceil((date.getMonth() + 1) / 3)
    },

    // Quarter: 1st, 2nd, 3rd, 4th
    Qo: function Qo (date) {
      return getOrdinal(this.Q(date))
    },

    // Day of month: 1, 2, ..., 31
    D: function D (date) {
      return date.getDate()
    },

    // Day of month: 1st, 2nd, ..., 31st
    Do: function Do (date) {
      return getOrdinal(date.getDate())
    },

    // Day of month: 01, 02, ..., 31
    DD: function DD (date) {
      return pad(date.getDate())
    },

    // Day of year: 1, 2, ..., 366
    DDD: function DDD (date) {
      return getDayOfYear(date)
    },

    // Day of year: 001, 002, ..., 366
    DDDD: function DDDD (date) {
      return pad(getDayOfYear(date), 3)
    },

    // Day of week: 0, 1, ..., 6
    d: function d (date) {
      return date.getDay()
    },

    // Day of week: Su, Mo, ...
    dd: function dd (date, dateLocale) {
      return this.dddd(date, dateLocale).slice(0, 2)
    },

    // Day of week: Sun, Mon, ...
    ddd: function ddd (date, dateLocale) {
      return dateLocale.daysShort[date.getDay()]
    },

    // Day of week: Sunday, Monday, ...
    dddd: function dddd (date, dateLocale) {
      return dateLocale.days[date.getDay()]
    },

    // Day of ISO week: 1, 2, ..., 7
    E: function E (date) {
      return date.getDay() || 7
    },

    // Week of Year: 1 2 ... 52 53
    w: function w (date) {
      return getWeekOfYear(date)
    },

    // Week of Year: 01 02 ... 52 53
    ww: function ww (date) {
      return pad(getWeekOfYear(date))
    },

    // Hour: 0, 1, ... 23
    H: function H (date) {
      return date.getHours()
    },

    // Hour: 00, 01, ..., 23
    HH: function HH (date) {
      return pad(date.getHours())
    },

    // Hour: 1, 2, ..., 12
    h: function h (date) {
      var hours = date.getHours();
      if (hours === 0) {
        return 12
      }
      if (hours > 12) {
        return hours % 12
      }
      return hours
    },

    // Hour: 01, 02, ..., 12
    hh: function hh (date) {
      return pad(this.h(date))
    },

    // Minute: 0, 1, ..., 59
    m: function m (date) {
      return date.getMinutes()
    },

    // Minute: 00, 01, ..., 59
    mm: function mm (date) {
      return pad(date.getMinutes())
    },

    // Second: 0, 1, ..., 59
    s: function s (date) {
      return date.getSeconds()
    },

    // Second: 00, 01, ..., 59
    ss: function ss (date) {
      return pad(date.getSeconds())
    },

    // 1/10 of second: 0, 1, ..., 9
    S: function S (date) {
      return Math.floor(date.getMilliseconds() / 100)
    },

    // 1/100 of second: 00, 01, ..., 99
    SS: function SS (date) {
      return pad(Math.floor(date.getMilliseconds() / 10))
    },

    // Millisecond: 000, 001, ..., 999
    SSS: function SSS (date) {
      return pad(date.getMilliseconds(), 3)
    },

    // Meridiem: AM, PM
    A: function A (date) {
      return this.H(date) < 12 ? 'AM' : 'PM'
    },

    // Meridiem: am, pm
    a: function a (date) {
      return this.H(date) < 12 ? 'am' : 'pm'
    },

    // Meridiem: a.m., p.m.
    aa: function aa (date) {
      return this.H(date) < 12 ? 'a.m.' : 'p.m.'
    },

    // Timezone: -01:00, +00:00, ... +12:00
    Z: function Z (date) {
      return formatTimezone(date.getTimezoneOffset(), ':')
    },

    // Timezone: -0100, +0000, ... +1200
    ZZ: function ZZ (date) {
      return formatTimezone(date.getTimezoneOffset())
    },

    // Seconds timestamp: 512969520
    X: function X (date) {
      return Math.floor(date.getTime() / 1000)
    },

    // Milliseconds timestamp: 512969520900
    x: function x (date) {
      return date.getTime()
    }
  };

  function formatDate (val, mask, dateLocale, __forcedYear) {
    if (
      (val !== 0 && !val) ||
      val === Infinity ||
      val === -Infinity
    ) {
      return
    }

    var date = new Date(val);

    if (isNaN(date)) {
      return
    }

    if (mask === void 0) {
      mask = defaultMask;
    }

    var locale = dateLocale !== void 0
      ? dateLocale
      : lang.props.date;

    return mask.replace(
      token,
      function (match, text) { return match in formatter
        ? formatter[match](date, locale, __forcedYear)
        : (text === void 0 ? match : text.split('\\]').join(']')); }
    )
  }

  function clone (date) {
    return isDate(date) === true
      ? new Date(date.getTime())
      : date
  }

  var date = {
    isValid: isValid,
    extractDate: extractDate,
    buildDate: buildDate,
    getDayOfWeek: getDayOfWeek,
    getWeekOfYear: getWeekOfYear,
    isBetweenDates: isBetweenDates,
    addToDate: addToDate,
    subtractFromDate: subtractFromDate,
    adjustDate: adjustDate,
    startOfDate: startOfDate,
    endOfDate: endOfDate,
    getMaxDate: getMaxDate,
    getMinDate: getMinDate,
    getDateDiff: getDateDiff,
    getDayOfYear: getDayOfYear,
    inferDateFormat: inferDateFormat,
    getDateBetween: getDateBetween,
    isSameDate: isSameDate,
    daysInMonth: daysInMonth,
    formatDate: formatDate,
    clone: clone
  };

  var yearsInterval = 20;
  var viewIsValid = function (v) { return ['Calendar', 'Years', 'Months'].includes(v); };

  var QDate = Vue.extend({
    name: 'QDate',

    mixins: [ DateTimeMixin ],

    props: {
      title: String,
      subtitle: String,

      emitImmediately: Boolean,

      mask: {
        // this mask is forced
        // when using persian calendar
        default: 'YYYY/MM/DD'
      },

      defaultYearMonth: {
        type: String,
        validator: function (v) { return /^-?[\d]+\/[0-1]\d$/.test(v); }
      },

      events: [Array, Function],
      eventColor: [String, Function],

      options: [Array, Function],

      firstDayOfWeek: [String, Number],
      todayBtn: Boolean,
      minimal: Boolean,
      defaultView: {
        type: String,
        default: 'Calendar',
        validator: viewIsValid
      }
    },

    data: function data () {
      var ref = this.__getModels(this.value, this.mask, this.__getComputedLocale());
      var inner = ref.inner;
      var external = ref.external;
      var direction = this.$q.lang.rtl === true ? 'right' : 'left';

      return {
        view: this.defaultView,
        monthDirection: direction,
        yearDirection: direction,
        startYear: inner.year - inner.year % yearsInterval,
        innerModel: inner,
        extModel: external
      }
    },

    watch: {
      value: function value (v) {
        var this$1 = this;

        var ref = this.__getModels(v, this.mask, this.__getComputedLocale());
        var inner = ref.inner;
        var external = ref.external;

        if (
          this.extModel.dateHash !== external.dateHash ||
          this.extModel.timeHash !== external.timeHash
        ) {
          this.extModel = external;
        }

        if (inner.dateHash !== this.innerModel.dateHash) {
          this.monthDirection = (this.innerModel.dateHash < inner.dateHash) === (this.$q.lang.rtl !== true) ? 'left' : 'right';
          if (inner.year !== this.innerModel.year) {
            this.yearDirection = this.monthDirection;
          }

          this.$nextTick(function () {
            this$1.startYear = inner.year - inner.year % yearsInterval;
            this$1.innerModel = inner;
          });
        }
      },

      view: function view () {
        this.$refs.blurTarget !== void 0 && this.$refs.blurTarget.focus();
      }
    },

    computed: {
      classes: function classes () {
        var type = this.landscape === true ? 'landscape' : 'portrait';
        return "q-date q-date--" + type + " q-date--" + type + "-" + (this.minimal === true ? 'minimal' : 'standard') +
          (this.isDark === true ? ' q-date--dark q-dark' : '') +
          (this.bordered === true ? " q-date--bordered" : '') +
          (this.square === true ? " q-date--square no-border-radius" : '') +
          (this.flat === true ? " q-date--flat no-shadow" : '') +
          (this.disable === true ? ' disabled' : (this.readonly === true ? ' q-date--readonly' : ''))
      },

      headerTitle: function headerTitle () {
        if (this.title !== void 0 && this.title !== null && this.title.length > 0) {
          return this.title
        }

        var model = this.extModel;
        if (model.dateHash === null) { return ' --- ' }

        var date;

        if (this.calendar !== 'persian') {
          date = new Date(model.year, model.month - 1, model.day);
        }
        else {
          var gDate = toGregorian(model.year, model.month, model.day);
          date = new Date(gDate.gy, gDate.gm - 1, gDate.gd);
        }

        if (isNaN(date.valueOf()) === true) { return ' --- ' }

        if (this.computedLocale.headerTitle !== void 0) {
          return this.computedLocale.headerTitle(date, model)
        }

        return this.computedLocale.daysShort[ date.getDay() ] + ', ' +
          this.computedLocale.monthsShort[ model.month - 1 ] + ' ' +
          model.day
      },

      headerSubtitle: function headerSubtitle () {
        return this.subtitle !== void 0 && this.subtitle !== null && this.subtitle.length > 0
          ? this.subtitle
          : (
            this.extModel.year !== null
              ? this.extModel.year
              : ' --- '
          )
      },

      dateArrow: function dateArrow () {
        var val = [ this.$q.iconSet.datetime.arrowLeft, this.$q.iconSet.datetime.arrowRight ];
        return this.$q.lang.rtl === true ? val.reverse() : val
      },

      computedFirstDayOfWeek: function computedFirstDayOfWeek () {
        return this.firstDayOfWeek !== void 0
          ? Number(this.firstDayOfWeek)
          : this.computedLocale.firstDayOfWeek
      },

      daysOfWeek: function daysOfWeek () {
        var
          days = this.computedLocale.daysShort,
          first = this.computedFirstDayOfWeek;

        return first > 0
          ? days.slice(first, 7).concat(days.slice(0, first))
          : days
      },

      daysInMonth: function daysInMonth () {
        return this.__getDaysInMonth(this.innerModel)
      },

      today: function today () {
        return this.__getCurrentDate()
      },

      evtFn: function evtFn () {
        var this$1 = this;

        return typeof this.events === 'function'
          ? this.events
          : function (date) { return this$1.events.includes(date); }
      },

      evtColor: function evtColor () {
        var this$1 = this;

        return typeof this.eventColor === 'function'
          ? this.eventColor
          : function (date) { return this$1.eventColor; }
      },

      isInSelection: function isInSelection () {
        var this$1 = this;

        return typeof this.options === 'function'
          ? this.options
          : function (date) { return this$1.options.includes(date); }
      },

      days: function days () {
        var date, endDay;

        var res = [];

        if (this.calendar !== 'persian') {
          date = new Date(this.innerModel.year, this.innerModel.month - 1, 1);
          endDay = (new Date(this.innerModel.year, this.innerModel.month - 1, 0)).getDate();
        }
        else {
          var gDate = toGregorian(this.innerModel.year, this.innerModel.month, 1);
          date = new Date(gDate.gy, gDate.gm - 1, gDate.gd);
          var prevJM = this.innerModel.month - 1;
          var prevJY = this.innerModel.year;
          if (prevJM === 0) {
            prevJM = 12;
            prevJY--;
          }
          endDay = jalaaliMonthLength(prevJY, prevJM);
        }

        var days = (date.getDay() - this.computedFirstDayOfWeek - 1);

        var len = days < 0 ? days + 7 : days;
        if (len < 6) {
          for (var i = endDay - len; i <= endDay; i++) {
            res.push({ i: i, fill: true });
          }
        }

        var
          index = res.length,
          prefix = this.innerModel.year + '/' + pad(this.innerModel.month) + '/';

        for (var i$1 = 1; i$1 <= this.daysInMonth; i$1++) {
          var day = prefix + pad(i$1);

          if (this.options !== void 0 && this.isInSelection(day) !== true) {
            res.push({ i: i$1 });
          }
          else {
            var event = this.events !== void 0 && this.evtFn(day) === true
              ? this.evtColor(day)
              : false;

            res.push({ i: i$1, in: true, flat: true, event: event });
          }
        }

        if (this.innerModel.year === this.extModel.year && this.innerModel.month === this.extModel.month) {
          var i$2 = index + this.innerModel.day - 1;
          res[i$2] !== void 0 && Object.assign(res[i$2], {
            unelevated: true,
            flat: false,
            color: this.computedColor,
            textColor: this.computedTextColor
          });
        }

        if (this.innerModel.year === this.today.year && this.innerModel.month === this.today.month) {
          res[index + this.today.day - 1].today = true;
        }

        var left = res.length % 7;
        if (left > 0) {
          var afterDays = 7 - left;
          for (var i$3 = 1; i$3 <= afterDays; i$3++) {
            res.push({ i: i$3, fill: true });
          }
        }

        return res
      },

      attrs: function attrs () {
        if (this.disable === true) {
          return { 'aria-disabled': '' }
        }
        if (this.readonly === true) {
          return { 'aria-readonly': '' }
        }
      }
    },

    methods: {
      setToday: function setToday () {
        this.__updateValue(Object.assign({}, this.today), 'today');
        this.view = 'Calendar';
      },

      setView: function setView (view) {
        if (viewIsValid(view) === true) {
          this.view = view;
        }
      },

      offsetCalendar: function offsetCalendar (type, descending) {
        if (['month', 'year'].includes(type)) {
          this[("__goTo" + (type === 'month' ? 'Month' : 'Year'))](
            descending === true ? -1 : 1
          );
        }
      },

      __getModels: function __getModels (val, mask, locale) {
        var external = __splitDate(
          val,
          this.calendar === 'persian' ? 'YYYY/MM/DD' : mask,
          locale,
          this.calendar
        );

        return {
          external: external,
          inner: external.dateHash === null
            ? this.__getDefaultModel()
            : Object.assign({}, external)
        }
      },

      __getDefaultModel: function __getDefaultModel () {
        var year, month;

        if (this.defaultYearMonth !== void 0) {
          var d = this.defaultYearMonth.split('/');
          year = parseInt(d[0], 10);
          month = parseInt(d[1], 10);
        }
        else {
          // may come from data() where computed
          // props are not yet available
          var d$1 = this.today !== void 0
            ? this.today
            : this.__getCurrentDate();

          year = d$1.year;
          month = d$1.month;
        }

        return {
          year: year,
          month: month,
          day: 1,
          hour: 0,
          minute: 0,
          second: 0,
          millisecond: 0,
          dateHash: year + '/' + pad(month) + '/01'
        }
      },

      __getHeader: function __getHeader (h) {
        var this$1 = this;

        if (this.minimal === true) { return }

        return h('div', {
          staticClass: 'q-date__header',
          class: this.headerClass
        }, [
          h('div', {
            staticClass: 'relative-position'
          }, [
            h('transition', {
              props: {
                name: 'q-transition--fade'
              }
            }, [
              h('div', {
                key: 'h-yr-' + this.headerSubtitle,
                staticClass: 'q-date__header-subtitle q-date__header-link',
                class: this.view === 'Years' ? 'q-date__header-link--active' : 'cursor-pointer',
                attrs: { tabindex: this.computedTabindex },
                on: cache(this, 'vY', {
                  click: function () { this$1.view = 'Years'; },
                  keyup: function (e) { e.keyCode === 13 && (this$1.view = 'Years'); }
                })
              }, [ this.headerSubtitle ])
            ])
          ]),

          h('div', {
            staticClass: 'q-date__header-title relative-position flex no-wrap'
          }, [
            h('div', {
              staticClass: 'relative-position col'
            }, [
              h('transition', {
                props: {
                  name: 'q-transition--fade'
                }
              }, [
                h('div', {
                  key: 'h-sub' + this.headerTitle,
                  staticClass: 'q-date__header-title-label q-date__header-link',
                  class: this.view === 'Calendar' ? 'q-date__header-link--active' : 'cursor-pointer',
                  attrs: { tabindex: this.computedTabindex },
                  on: cache(this, 'vC', {
                    click: function () { this$1.view = 'Calendar'; },
                    keyup: function (e) { e.keyCode === 13 && (this$1.view = 'Calendar'); }
                  })
                }, [ this.headerTitle ])
              ])
            ]),

            this.todayBtn === true ? h(QBtn, {
              staticClass: 'q-date__header-today',
              props: {
                icon: this.$q.iconSet.datetime.today,
                flat: true,
                size: 'sm',
                round: true,
                tabindex: this.computedTabindex
              },
              on: cache(this, 'today', { click: this.setToday })
            }) : null
          ])
        ])
      },

      __getNavigation: function __getNavigation (h, ref) {
        var this$1 = this;
        var label = ref.label;
        var view = ref.view;
        var key = ref.key;
        var dir = ref.dir;
        var goTo = ref.goTo;
        var cls = ref.cls;

        return [
          h('div', {
            staticClass: 'row items-center q-date__arrow'
          }, [
            h(QBtn, {
              props: {
                round: true,
                dense: true,
                size: 'sm',
                flat: true,
                icon: this.dateArrow[0],
                tabindex: this.computedTabindex
              },
              on: cache(this, 'go-#' + view, { click: function click () { goTo(-1); } })
            })
          ]),

          h('div', {
            staticClass: 'relative-position overflow-hidden flex flex-center' + cls
          }, [
            h('transition', {
              props: {
                name: 'q-transition--jump-' + dir
              }
            }, [
              h('div', { key: key }, [
                h(QBtn, {
                  props: {
                    flat: true,
                    dense: true,
                    noCaps: true,
                    label: label,
                    tabindex: this.computedTabindex
                  },
                  on: cache(this, 'view#' + view, { click: function () { this$1.view = view; } })
                })
              ])
            ])
          ]),

          h('div', {
            staticClass: 'row items-center q-date__arrow'
          }, [
            h(QBtn, {
              props: {
                round: true,
                dense: true,
                size: 'sm',
                flat: true,
                icon: this.dateArrow[1],
                tabindex: this.computedTabindex
              },
              on: cache(this, 'go+#' + view, { click: function click () { goTo(1); } })
            })
          ])
        ]
      },

      __getCalendarView: function __getCalendarView (h) {
        var this$1 = this;

        return [
          h('div', {
            key: 'calendar-view',
            staticClass: 'q-date__view q-date__calendar'
          }, [
            h('div', {
              staticClass: 'q-date__navigation row items-center no-wrap'
            }, this.__getNavigation(h, {
              label: this.computedLocale.months[ this.innerModel.month - 1 ],
              view: 'Months',
              key: this.innerModel.month,
              dir: this.monthDirection,
              goTo: this.__goToMonth,
              cls: ' col'
            }).concat(this.__getNavigation(h, {
              label: this.innerModel.year,
              view: 'Years',
              key: this.innerModel.year,
              dir: this.yearDirection,
              goTo: this.__goToYear,
              cls: ''
            }))),

            h('div', {
              staticClass: 'q-date__calendar-weekdays row items-center no-wrap'
            }, this.daysOfWeek.map(function (day) { return h('div', { staticClass: 'q-date__calendar-item' }, [ h('div', [ day ]) ]); })),

            h('div', {
              staticClass: 'q-date__calendar-days-container relative-position overflow-hidden'
            }, [
              h('transition', {
                props: {
                  name: 'q-transition--slide-' + this.monthDirection
                }
              }, [
                h('div', {
                  key: this.innerModel.year + '/' + this.innerModel.month,
                  staticClass: 'q-date__calendar-days fit'
                }, this.days.map(function (day) { return h('div', {
                  staticClass: ("q-date__calendar-item q-date__calendar-item--" + (day.fill === true ? 'fill' : (day.in === true ? 'in' : 'out')))
                }, [
                  day.in === true
                    ? h(QBtn, {
                      staticClass: day.today === true ? 'q-date__today' : null,
                      props: {
                        dense: true,
                        flat: day.flat,
                        unelevated: day.unelevated,
                        color: day.color,
                        textColor: day.textColor,
                        label: day.i,
                        tabindex: this$1.computedTabindex
                      },
                      on: cache(this$1, 'day#' + day.i, { click: function () { this$1.__setDay(day.i); } })
                    }, day.event !== false ? [
                      h('div', { staticClass: 'q-date__event bg-' + day.event })
                    ] : null)
                    : h('div', [ day.i ])
                ]); }))
              ])
            ])
          ])
        ]
      },

      __getMonthsView: function __getMonthsView (h) {
        var this$1 = this;

        var currentYear = this.innerModel.year === this.today.year;

        var content = this.computedLocale.monthsShort.map(function (month, i) {
          var active = this$1.innerModel.month === i + 1;

          return h('div', {
            staticClass: 'q-date__months-item flex flex-center'
          }, [
            h(QBtn, {
              staticClass: currentYear === true && this$1.today.month === i + 1 ? 'q-date__today' : null,
              props: {
                flat: !active,
                label: month,
                unelevated: active,
                color: active ? this$1.computedColor : null,
                textColor: active ? this$1.computedTextColor : null,
                tabindex: this$1.computedTabindex
              },
              on: cache(this$1, 'month#' + i, { click: function () { this$1.__setMonth(i + 1); } })
            })
          ])
        });

        return h('div', {
          key: 'months-view',
          staticClass: 'q-date__view q-date__months flex flex-center'
        }, content)
      },

      __getYearsView: function __getYearsView (h) {
        var this$1 = this;

        var
          start = this.startYear,
          stop = start + yearsInterval,
          years = [];

        var loop = function ( i ) {
          var active = this$1.innerModel.year === i;

          years.push(
            h('div', {
              staticClass: 'q-date__years-item flex flex-center'
            }, [
              h(QBtn, {
                key: 'yr' + i,
                staticClass: this$1.today.year === i ? 'q-date__today' : null,
                props: {
                  flat: !active,
                  label: i,
                  dense: true,
                  unelevated: active,
                  color: active ? this$1.computedColor : null,
                  textColor: active ? this$1.computedTextColor : null,
                  tabindex: this$1.computedTabindex
                },
                on: cache(this$1, 'yr#' + i, { click: function () { this$1.__setYear(i); } })
              })
            ])
          );
        };

        for (var i = start; i <= stop; i++) loop( i );

        return h('div', {
          staticClass: 'q-date__view q-date__years flex flex-center'
        }, [
          h('div', {
            staticClass: 'col-auto'
          }, [
            h(QBtn, {
              props: {
                round: true,
                dense: true,
                flat: true,
                icon: this.dateArrow[0],
                tabindex: this.computedTabindex
              },
              on: cache(this, 'y-', { click: function () { this$1.startYear -= yearsInterval; } })
            })
          ]),

          h('div', {
            staticClass: 'q-date__years-content col self-stretch row items-center'
          }, years),

          h('div', {
            staticClass: 'col-auto'
          }, [
            h(QBtn, {
              props: {
                round: true,
                dense: true,
                flat: true,
                icon: this.dateArrow[1],
                tabindex: this.computedTabindex
              },
              on: cache(this, 'y+', { click: function () { this$1.startYear += yearsInterval; } })
            })
          ])
        ])
      },

      __getDaysInMonth: function __getDaysInMonth (obj) {
        return this.calendar !== 'persian'
          ? (new Date(obj.year, obj.month, 0)).getDate()
          : jalaaliMonthLength(obj.year, obj.month)
      },

      __goToMonth: function __goToMonth (offset) {
        var
          month = Number(this.innerModel.month) + offset,
          yearDir = this.yearDirection;

        if (month === 13) {
          month = 1;
          this.innerModel.year++;
          yearDir = (this.$q.lang.rtl !== true) ? 'left' : 'right';
        }
        else if (month === 0) {
          month = 12;
          this.innerModel.year--;
          yearDir = (this.$q.lang.rtl !== true) ? 'right' : 'left';
        }

        this.monthDirection = (offset > 0) === (this.$q.lang.rtl !== true) ? 'left' : 'right';
        this.yearDirection = yearDir;
        this.innerModel.month = month;
        this.emitImmediately === true && this.__updateValue({}, 'month');
      },

      __goToYear: function __goToYear (offset) {
        this.monthDirection = this.yearDirection = (offset > 0) === (this.$q.lang.rtl !== true) ? 'left' : 'right';
        this.innerModel.year = Number(this.innerModel.year) + offset;
        this.emitImmediately === true && this.__updateValue({}, 'year');
      },

      __setYear: function __setYear (year) {
        this.innerModel.year = year;
        this.emitImmediately === true && this.__updateValue({ year: year }, 'year');
        this.view = this.extModel.month === null || this.defaultView === 'Years' ? 'Months' : 'Calendar';
      },

      __setMonth: function __setMonth (month) {
        this.innerModel.month = month;
        this.emitImmediately === true && this.__updateValue({ month: month }, 'month');
        this.view = 'Calendar';
      },

      __setDay: function __setDay (day) {
        this.__updateValue({ day: day }, 'day');
      },

      __updateValue: function __updateValue (date, reason) {
        var this$1 = this;

        if (date.year === void 0) {
          date.year = this.innerModel.year;
        }
        if (date.month === void 0) {
          date.month = this.innerModel.month;
        }
        if (
          date.day === void 0 ||
          (this.emitImmediately === true && (reason === 'year' || reason === 'month'))
        ) {
          date.day = this.innerModel.day;
          var maxDay = this.emitImmediately === true
            ? this.__getDaysInMonth(date)
            : this.daysInMonth;

          date.day = Math.min(date.day, maxDay);
        }

        var val = this.calendar === 'persian'
          ? date.year + '/' + pad(date.month) + '/' + pad(date.day)
          : formatDate(
            new Date(
              date.year,
              date.month - 1,
              date.day,
              this.extModel.hour,
              this.extModel.minute,
              this.extModel.second,
              this.extModel.millisecond
            ),
            this.mask,
            this.computedLocale,
            date.year
          );

        date.changed = val !== this.value;
        this.$emit('input', val, reason, date);

        if (val === this.value && reason === 'today') {
          var newHash = date.year + '/' + pad(date.month) + '/' + pad(date.day);
          var curHash = this.innerModel.year + '/' + pad(this.innerModel.month) + '/' + pad(this.innerModel.day);

          if (newHash !== curHash) {
            this.monthDirection = (curHash < newHash) === (this.$q.lang.rtl !== true) ? 'left' : 'right';
            if (date.year !== this.innerModel.year) {
              this.yearDirection = this.monthDirection;
            }

            this.$nextTick(function () {
              this$1.startYear = date.year - date.year % yearsInterval;
              Object.assign(this$1.innerModel, {
                year: date.year,
                month: date.month,
                day: date.day,
                dateHash: newHash
              });
            });
          }
        }
      }
    },

    render: function render (h) {
      var content = [
        h('div', {
          staticClass: 'q-date__content col relative-position'
        }, [
          h('transition', {
            props: { name: 'q-transition--fade' }
          }, [
            this[("__get" + (this.view) + "View")](h)
          ])
        ])
      ];

      var def = slot(this, 'default');
      def !== void 0 && content.push(
        h('div', { staticClass: 'q-date__actions' }, def)
      );

      if (this.name !== void 0 && this.disable !== true) {
        this.__injectFormInput(content, 'push');
      }

      return h('div', {
        class: this.classes,
        attrs: this.attrs,
        on: this.$listeners
      }, [
        this.__getHeader(h),

        h('div', {
          staticClass: 'q-date__main col column',
          attrs: { tabindex: -1 },
          ref: 'blurTarget'
        }, content)
      ])
    }
  });

  var HistoryMixin = {
    methods: {
      __addHistory: function __addHistory () {
        var this$1 = this;

        this.__historyEntry = {
          condition: function () { return this$1.hideOnRouteChange === true },
          handler: this.hide
        };
        History.add(this.__historyEntry);
      },

      __removeHistory: function __removeHistory () {
        if (this.__historyEntry !== void 0) {
          History.remove(this.__historyEntry);
          this.__historyEntry = void 0;
        }
      }
    },

    beforeDestroy: function beforeDestroy () {
      this.showing === true && this.__removeHistory();
    }
  };

  var
    registered = 0,
    scrollPositionX,
    scrollPositionY,
    maxScrollTop,
    vpPendingUpdate = false,
    bodyLeft,
    bodyTop,
    closeTimer;

  function onWheel (e) {
    if (shouldPreventScroll(e)) {
      stopAndPrevent(e);
    }
  }

  function shouldPreventScroll (e) {
    if (e.target === document.body || e.target.classList.contains('q-layout__backdrop')) {
      return true
    }

    var
      path = getEventPath(e),
      shift = e.shiftKey && !e.deltaX,
      scrollY = !shift && Math.abs(e.deltaX) <= Math.abs(e.deltaY),
      delta = shift || scrollY ? e.deltaY : e.deltaX;

    for (var index = 0; index < path.length; index++) {
      var el = path[index];

      if (hasScrollbar(el, scrollY)) {
        return scrollY
          ? (
            delta < 0 && el.scrollTop === 0
              ? true
              : delta > 0 && el.scrollTop + el.clientHeight === el.scrollHeight
          )
          : (
            delta < 0 && el.scrollLeft === 0
              ? true
              : delta > 0 && el.scrollLeft + el.clientWidth === el.scrollWidth
          )
      }
    }

    return true
  }

  function onAppleScroll (e) {
    if (e.target === document) {
      // required, otherwise iOS blocks further scrolling
      // until the mobile scrollbar dissapears
      document.scrollingElement.scrollTop = document.scrollingElement.scrollTop; // eslint-disable-line
    }
  }

  function onAppleResize (evt) {
    if (vpPendingUpdate === true) {
      return
    }

    vpPendingUpdate = true;

    requestAnimationFrame(function () {
      vpPendingUpdate = false;

      var ref = evt.target;
      var height = ref.height;
      var ref$1 = document.scrollingElement;
      var clientHeight = ref$1.clientHeight;
      var scrollTop = ref$1.scrollTop;

      if (maxScrollTop === void 0 || height !== window.innerHeight) {
        maxScrollTop = clientHeight - height;
        document.scrollingElement.scrollTop = scrollTop;
      }

      if (scrollTop > maxScrollTop) {
        document.scrollingElement.scrollTop -= Math.ceil((scrollTop - maxScrollTop) / 8);
      }
    });
  }

  function apply (action, is) {
    var
      body = document.body,
      hasViewport = window.visualViewport !== void 0;

    if (action === 'add') {
      var overflowY = window.getComputedStyle(body).overflowY;

      scrollPositionX = getHorizontalScrollPosition(window);
      scrollPositionY = getScrollPosition(window);
      bodyLeft = body.style.left;
      bodyTop = body.style.top;

      body.style.left = "-" + scrollPositionX + "px";
      body.style.top = "-" + scrollPositionY + "px";
      if (overflowY !== 'hidden' && (overflowY === 'scroll' || body.scrollHeight > window.innerHeight)) {
        body.classList.add('q-body--force-scrollbar');
      }

      body.classList.add('q-body--prevent-scroll');
      if (is.ios === true) {
        if (hasViewport === true) {
          window.scrollTo(0, 0);
          window.visualViewport.addEventListener('resize', onAppleResize, listenOpts.passiveCapture);
          window.visualViewport.addEventListener('scroll', onAppleResize, listenOpts.passiveCapture);
          window.scrollTo(0, 0);
        }
        else {
          window.addEventListener('scroll', onAppleScroll, listenOpts.passiveCapture);
        }
      }
    }

    if (is.desktop === true && is.mac === true) {
      // ref. https://developers.google.com/web/updates/2017/01/scrolling-intervention
      window[(action + "EventListener")]('wheel', onWheel, listenOpts.notPassive);
    }

    if (action === 'remove') {
      if (is.ios === true) {
        if (hasViewport === true) {
          window.visualViewport.removeEventListener('resize', onAppleResize, listenOpts.passiveCapture);
          window.visualViewport.removeEventListener('scroll', onAppleResize, listenOpts.passiveCapture);
        }
        else {
          window.removeEventListener('scroll', onAppleScroll, listenOpts.passiveCapture);
        }
      }

      body.classList.remove('q-body--prevent-scroll');
      body.classList.remove('q-body--force-scrollbar');

      body.style.left = bodyLeft;
      body.style.top = bodyTop;

      window.scrollTo(scrollPositionX, scrollPositionY);
      maxScrollTop = void 0;
    }
  }

  function preventScroll (state, is) {
    var action = 'add';

    if (state === true) {
      registered++;

      if (closeTimer !== void 0) {
        clearTimeout(closeTimer);
        closeTimer = void 0;
        return
      }

      if (registered > 1) {
        return
      }
    }
    else {
      if (registered === 0) {
        return
      }

      registered--;

      if (registered > 0) {
        return
      }

      action = 'remove';

      if (is.ios === true && is.nativeMobile === true) {
        clearTimeout(closeTimer);

        closeTimer = setTimeout(function () {
          apply(action, is);
          closeTimer = void 0;
        }, 100);
        return
      }
    }

    apply(action, is);
  }

  var PreventScrollMixin = {
    methods: {
      __preventScroll: function __preventScroll (state) {
        if (
          state !== this.preventedScroll &&
          (this.preventedScroll !== void 0 || state === true)
        ) {
          this.preventedScroll = state;
          preventScroll(state, this.$q.platform.is);
        }
      }
    }
  };

  var maximizedModals = 0;

  var positionClass = {
    standard: 'fixed-full flex-center',
    top: 'fixed-top justify-center',
    bottom: 'fixed-bottom justify-center',
    right: 'fixed-right items-center',
    left: 'fixed-left items-center'
  };

  var transitions = {
    standard: ['scale', 'scale'],
    top: ['slide-down', 'slide-up'],
    bottom: ['slide-up', 'slide-down'],
    right: ['slide-left', 'slide-right'],
    left: ['slide-right', 'slide-left']
  };

  var QDialog = Vue.extend({
    name: 'QDialog',

    mixins: [ HistoryMixin, ModelToggleMixin, PortalMixin, PreventScrollMixin ],

    props: {
      persistent: Boolean,
      autoClose: Boolean,

      noEscDismiss: Boolean,
      noBackdropDismiss: Boolean,
      noRouteDismiss: Boolean,
      noRefocus: Boolean,
      noFocus: Boolean,

      seamless: Boolean,

      maximized: Boolean,
      fullWidth: Boolean,
      fullHeight: Boolean,

      square: Boolean,

      position: {
        type: String,
        default: 'standard',
        validator: function (val) { return val === 'standard' ||
          ['top', 'bottom', 'left', 'right'].includes(val); }
      },

      transitionShow: String,
      transitionHide: String
    },

    data: function data () {
      return {
        transitionState: this.showing
      }
    },

    watch: {
      showing: function showing (val) {
        var this$1 = this;

        if (this.transitionShowComputed !== this.transitionHideComputed) {
          this.$nextTick(function () {
            this$1.transitionState = val;
          });
        }
      },

      maximized: function maximized (newV, oldV) {
        if (this.showing === true) {
          this.__updateState(false, oldV);
          this.__updateState(true, newV);
        }
      },

      useBackdrop: function useBackdrop (v) {
        this.__preventScroll(v);
        this.__preventFocusout(v);
      }
    },

    computed: {
      classes: function classes () {
        return "q-dialog__inner--" + (this.maximized === true ? 'maximized' : 'minimized') + " " +
          "q-dialog__inner--" + (this.position) + " " + (positionClass[this.position]) +
          (this.fullWidth === true ? ' q-dialog__inner--fullwidth' : '') +
          (this.fullHeight === true ? ' q-dialog__inner--fullheight' : '') +
          (this.square === true ? ' q-dialog__inner--square' : '')
      },

      transitionShowComputed: function transitionShowComputed () {
        return 'q-transition--' + (this.transitionShow === void 0 ? transitions[this.position][0] : this.transitionShow)
      },

      transitionHideComputed: function transitionHideComputed () {
        return 'q-transition--' + (this.transitionHide === void 0 ? transitions[this.position][1] : this.transitionHide)
      },

      transition: function transition () {
        return this.transitionState === true
          ? this.transitionHideComputed
          : this.transitionShowComputed
      },

      useBackdrop: function useBackdrop () {
        return this.showing === true && this.seamless !== true
      },

      hideOnRouteChange: function hideOnRouteChange () {
        return this.persistent !== true &&
          this.noRouteDismiss !== true &&
          this.seamless !== true
      }
    },

    methods: {
      focus: function focus () {
        var node = this.__getInnerNode();

        if (node === void 0 || node.contains(document.activeElement) === true) {
          return
        }

        node = node.querySelector('[autofocus], [data-autofocus]') || node;
        node.focus();
      },

      shake: function shake () {
        this.focus();

        var node = this.__getInnerNode();

        if (node !== void 0) {
          node.classList.remove('q-animate--scale');
          node.classList.add('q-animate--scale');
          clearTimeout(this.shakeTimeout);
          this.shakeTimeout = setTimeout(function () {
            node.classList.remove('q-animate--scale');
          }, 170);
        }
      },

      __getInnerNode: function __getInnerNode () {
        return this.__portal !== void 0 && this.__portal.$refs !== void 0
          ? this.__portal.$refs.inner
          : void 0
      },

      __show: function __show (evt) {
        var this$1 = this;

        this.__addHistory();

        // IE can have null document.activeElement
        this.__refocusTarget = this.noRefocus === false && document.activeElement !== null
          ? document.activeElement
          : void 0;

        this.$el.dispatchEvent(create('popup-show', { bubbles: true }));

        this.__updateState(true, this.maximized);

        EscapeKey.register(this, function () {
          if (this$1.seamless !== true) {
            if (this$1.persistent === true || this$1.noEscDismiss === true) {
              this$1.maximized !== true && this$1.shake();
            }
            else {
              this$1.$emit('escape-key');
              this$1.hide();
            }
          }
        });

        this.__showPortal();

        if (this.noFocus !== true) {
          // IE can have null document.activeElement
          document.activeElement !== null && document.activeElement.blur();
          this.__nextTick(this.focus);
        }

        this.__setTimeout(function () {
          if (this$1.$q.platform.is.ios === true && document.activeElement) {
            var ref = document.activeElement.getBoundingClientRect();
            var top = ref.top;
            var bottom = ref.bottom;
            var innerHeight = window.innerHeight;
            var height = window.visualViewport !== void 0
                ? window.visualViewport.height
                : innerHeight;

            if (top > 0 && bottom > height / 2) {
              var scrollTop = Math.min(
                document.scrollingElement.scrollHeight - height,
                bottom >= innerHeight
                  ? Infinity
                  : Math.ceil(document.scrollingElement.scrollTop + bottom - height / 2)
              );

              var fn = function () {
                requestAnimationFrame(function () {
                  document.scrollingElement.scrollTop += Math.ceil((scrollTop - document.scrollingElement.scrollTop) / 8);
                  if (document.scrollingElement.scrollTop !== scrollTop) {
                    fn();
                  }
                });
              };

              fn();
            }
            document.activeElement.scrollIntoView();
          }

          // required in order to avoid the "double-tap needed" issue
          this$1.$q.platform.is.ios === true && this$1.__portal.$el.click();

          this$1.$emit('show', evt);
        }, 300);
      },

      __hide: function __hide (evt) {
        var this$1 = this;

        this.__removeHistory();
        this.__cleanup(true);

        // check null for IE
        if (this.__refocusTarget !== void 0 && this.__refocusTarget !== null) {
          this.__refocusTarget.focus();
        }

        this.$el.dispatchEvent(create('popup-hide', { bubbles: true }));

        this.__setTimeout(function () {
          this$1.__hidePortal();
          this$1.$emit('hide', evt);
        }, 300);
      },

      __cleanup: function __cleanup (hiding) {
        clearTimeout(this.shakeTimeout);

        if (hiding === true || this.showing === true) {
          EscapeKey.pop(this);
          this.__updateState(false, this.maximized);
          if (this.seamless !== true) {
            this.__preventScroll(false);
            this.__preventFocusout(false);
          }
        }
      },

      __updateState: function __updateState (opening, maximized) {
        if (maximized === true) {
          if (opening === true) {
            maximizedModals < 1 && document.body.classList.add('q-body--dialog');
          }
          else if (maximizedModals < 2) {
            document.body.classList.remove('q-body--dialog');
          }
          maximizedModals += opening === true ? 1 : -1;
        }
      },

      __preventFocusout: function __preventFocusout (state) {
        if (this.$q.platform.is.desktop === true) {
          var action = (state === true ? 'add' : 'remove') + "EventListener";
          document.body[action]('focusin', this.__onFocusChange);
        }
      },

      __onAutoClose: function __onAutoClose (e) {
        this.hide(e);
        this.$listeners.click !== void 0 && this.$emit('click', e);
      },

      __onBackdropClick: function __onBackdropClick (e) {
        if (this.persistent !== true && this.noBackdropDismiss !== true) {
          this.hide(e);
        }
        else {
          this.shake();
        }
      },

      __onFocusChange: function __onFocusChange (e) {
        // the focus is not in a vue child component
        if (
          this.showing === true &&
          this.__portal !== void 0 &&
          childHasFocus(this.__portal.$el, e.target) !== true
        ) {
          this.focus();
        }
      },

      __renderPortal: function __renderPortal (h) {
        var on = Object.assign({}, this.$listeners,
          // stop propagating these events from children
          {input: stop,
          'popup-show': stop,
          'popup-hide': stop});

        if (this.autoClose === true) {
          on.click = this.__onAutoClose;
        }

        return h('div', {
          staticClass: 'q-dialog fullscreen no-pointer-events',
          class: this.contentClass,
          style: this.contentStyle,
          attrs: this.$attrs
        }, [
          h('transition', {
            props: { name: 'q-transition--fade' }
          }, this.useBackdrop === true ? [
            h('div', {
              staticClass: 'q-dialog__backdrop fixed-full',
              on: cache(this, 'bkdrop', {
                click: this.__onBackdropClick
              })
            })
          ] : null),

          h('transition', {
            props: { name: this.transition }
          }, [
            this.showing === true ? h('div', {
              ref: 'inner',
              staticClass: 'q-dialog__inner flex no-pointer-events',
              class: this.classes,
              attrs: { tabindex: -1 },
              on: on
            }, slot(this, 'default')) : null
          ])
        ])
      }
    },

    mounted: function mounted () {
      this.__processModelChange(this.value);
    },

    beforeDestroy: function beforeDestroy () {
      this.__cleanup();
    }
  });

  var duration = 150;

  var mouseEvents = [
    'mouseover', 'mouseout', 'mouseenter', 'mouseleave'
  ];

  var QDrawer = Vue.extend({
    name: 'QDrawer',

    inject: {
      layout: {
        default: function default$1 () {
          console.error('QDrawer needs to be child of QLayout');
        }
      }
    },

    mixins: [ DarkMixin, HistoryMixin, ModelToggleMixin, PreventScrollMixin ],

    directives: {
      TouchPan: TouchPan
    },

    props: {
      side: {
        type: String,
        default: 'left',
        validator: function (v) { return ['left', 'right'].includes(v); }
      },

      width: {
        type: Number,
        default: 300
      },

      mini: Boolean,
      miniToOverlay: Boolean,
      miniWidth: {
        type: Number,
        default: 57
      },

      breakpoint: {
        type: Number,
        default: 1023
      },
      showIfAbove: Boolean,

      behavior: {
        type: String,
        validator: function (v) { return ['default', 'desktop', 'mobile'].includes(v); },
        default: 'default'
      },

      bordered: Boolean,
      elevated: Boolean,
      contentStyle: [String, Object, Array],
      contentClass: [String, Object, Array],

      overlay: Boolean,
      persistent: Boolean,
      noSwipeOpen: Boolean,
      noSwipeClose: Boolean,
      noSwipeBackdrop: Boolean
    },

    data: function data () {
      var belowBreakpoint = (
        this.behavior === 'mobile' ||
        (this.behavior !== 'desktop' && this.layout.totalWidth <= this.breakpoint)
      );

      return {
        belowBreakpoint: belowBreakpoint,
        showing: this.showIfAbove === true && belowBreakpoint === false
          ? true
          : this.value === true
      }
    },

    watch: {
      belowBreakpoint: function belowBreakpoint (val) {
        if (val === true) { // from lg to xs
          this.lastDesktopState = this.showing;
          this.showing === true && this.hide(false);
        }
        else if (
          this.overlay === false &&
          this.behavior !== 'mobile' &&
          this.lastDesktopState !== false
        ) { // from xs to lg
          if (this.showing === true) {
            this.__applyPosition(0);
            this.__applyBackdrop(0);
            this.__cleanup();
          }
          else {
            this.show(false);
          }
        }
      },

      'layout.totalWidth': function layout_totalWidth (val) {
        this.__updateLocal('belowBreakpoint', (
          this.behavior === 'mobile' ||
          (this.behavior !== 'desktop' && val <= this.breakpoint)
        ));
      },

      side: function side (_, oldSide) {
        this.layout[oldSide].space = false;
        this.layout[oldSide].offset = 0;
      },

      behavior: function behavior (val) {
        this.__updateLocal('belowBreakpoint', (
          val === 'mobile' ||
          (val !== 'desktop' && this.layout.totalWidth <= this.breakpoint)
        ));
      },

      breakpoint: function breakpoint (val) {
        this.__updateLocal('belowBreakpoint', (
          this.behavior === 'mobile' ||
          (this.behavior !== 'desktop' && this.layout.totalWidth <= val)
        ));
      },

      'layout.container': function layout_container (val) {
        this.showing === true && this.__preventScroll(val !== true);
      },

      'layout.scrollbarWidth': function layout_scrollbarWidth () {
        this.__applyPosition(this.showing === true ? 0 : void 0);
      },

      offset: function offset (val) {
        this.__update('offset', val);
      },

      onLayout: function onLayout (val) {
        this.$emit('on-layout', val);
        this.__update('space', val);
      },

      rightSide: function rightSide () {
        this.__applyPosition();
      },

      size: function size (val) {
        this.__applyPosition();
        this.__updateSizeOnLayout(this.miniToOverlay, val);
      },

      miniToOverlay: function miniToOverlay (val) {
        this.__updateSizeOnLayout(val, this.size);
      },

      '$q.lang.rtl': function $q_lang_rtl () {
        this.__applyPosition();
      },

      mini: function mini () {
        if (this.value === true) {
          this.__animateMini();
          this.layout.__animate();
        }
      },

      isMini: function isMini (val) {
        this.$emit('mini-state', val);
      }
    },

    computed: {
      rightSide: function rightSide () {
        return this.side === 'right'
      },

      otherSide: function otherSide () {
        return this.rightSide === true ? 'left' : 'right'
      },

      offset: function offset () {
        return this.showing === true && this.belowBreakpoint === false && this.overlay === false
          ? (this.miniToOverlay === true ? this.miniWidth : this.size)
          : 0
      },

      size: function size () {
        return this.isMini === true
          ? this.miniWidth
          : this.width
      },

      fixed: function fixed () {
        return this.overlay === true ||
          this.miniToOverlay === true ||
          this.layout.view.indexOf(this.rightSide ? 'R' : 'L') > -1 ||
          (this.$q.platform.is.ios && this.layout.container === true)
      },

      onLayout: function onLayout () {
        return this.showing === true && this.belowBreakpoint === false && this.overlay === false
      },

      onScreenOverlay: function onScreenOverlay () {
        return this.showing === true && this.belowBreakpoint === false && this.overlay === true
      },

      backdropClass: function backdropClass () {
        return this.showing === false ? 'no-pointer-events' : null
      },

      headerSlot: function headerSlot () {
        return this.rightSide === true
          ? this.layout.rows.top[2] === 'r'
          : this.layout.rows.top[0] === 'l'
      },

      footerSlot: function footerSlot () {
        return this.rightSide === true
          ? this.layout.rows.bottom[2] === 'r'
          : this.layout.rows.bottom[0] === 'l'
      },

      aboveStyle: function aboveStyle () {
        var css = {};

        if (this.layout.header.space === true && this.headerSlot === false) {
          if (this.fixed === true) {
            css.top = (this.layout.header.offset) + "px";
          }
          else if (this.layout.header.space === true) {
            css.top = (this.layout.header.size) + "px";
          }
        }

        if (this.layout.footer.space === true && this.footerSlot === false) {
          if (this.fixed === true) {
            css.bottom = (this.layout.footer.offset) + "px";
          }
          else if (this.layout.footer.space === true) {
            css.bottom = (this.layout.footer.size) + "px";
          }
        }

        return css
      },

      style: function style () {
        var style = { width: ((this.size) + "px") };
        return this.belowBreakpoint === true
          ? style
          : Object.assign(style, this.aboveStyle)
      },

      classes: function classes () {
        return "q-drawer--" + (this.side) +
          (this.bordered === true ? ' q-drawer--bordered' : '') +
          (this.isDark === true ? ' q-drawer--dark q-dark' : '') +
          (
            this.belowBreakpoint === true
              ? ' fixed q-drawer--on-top q-drawer--mobile q-drawer--top-padding'
              : " q-drawer--" + (this.isMini === true ? 'mini' : 'standard') +
              (this.fixed === true || this.onLayout !== true ? ' fixed' : '') +
              (this.overlay === true || this.miniToOverlay === true ? ' q-drawer--on-top' : '') +
              (this.headerSlot === true ? ' q-drawer--top-padding' : '')
          )
      },

      stateDirection: function stateDirection () {
        return (this.$q.lang.rtl === true ? -1 : 1) * (this.rightSide === true ? 1 : -1)
      },

      isMini: function isMini () {
        return this.mini === true && this.belowBreakpoint !== true
      },

      onNativeEvents: function onNativeEvents () {
        var this$1 = this;

        if (this.belowBreakpoint !== true) {
          var evt = {
            '!click': function (e) { this$1.$emit('click', e); }
          };

          mouseEvents.forEach(function (name) {
            evt[name] = function (e) {
              this$1.$listeners[name] !== void 0 && this$1.$emit(name, e);
            };
          });

          return evt
        }
      },

      hideOnRouteChange: function hideOnRouteChange () {
        return this.persistent !== true &&
          (this.belowBreakpoint === true || this.onScreenOverlay === true)
      },

      openDirective: function openDirective () {
        var obj;

        var dir = this.$q.lang.rtl === true ? this.side : this.otherSide;

        return [{
          name: 'touch-pan',
          value: this.__openByTouch,
          modifiers: ( obj = {}, obj[ dir ] = true, obj.mouse = true, obj )
        }]
      },

      contentCloseDirective: function contentCloseDirective () {
        var obj;

        if (this.noSwipeClose !== true) {
          var dir = this.$q.lang.rtl === true ? this.otherSide : this.side;

          return [{
            name: 'touch-pan',
            value: this.__closeByTouch,
            modifiers: ( obj = {}, obj[ dir ] = true, obj.mouse = true, obj )
          }]
        }
      },

      backdropCloseDirective: function backdropCloseDirective () {
        var obj;

        if (this.noSwipeBackdrop !== true) {
          var dir = this.$q.lang.rtl === true ? this.otherSide : this.side;

          return [{
            name: 'touch-pan',
            value: this.__closeByTouch,
            modifiers: ( obj = {}, obj[ dir ] = true, obj.mouse = true, obj.mouseAllDir = true, obj )
          }]
        }
      }
    },

    methods: {
      __applyPosition: function __applyPosition (position) {
        var this$1 = this;

        if (position === void 0) {
          this.$nextTick(function () {
            position = this$1.showing === true ? 0 : this$1.size;
            this$1.__applyPosition(this$1.stateDirection * position);
          });
        }
        else if (this.$refs.content !== void 0) {
          if (
            this.layout.container === true &&
            this.rightSide === true &&
            (this.belowBreakpoint === true || Math.abs(position) === this.size)
          ) {
            position += this.stateDirection * this.layout.scrollbarWidth;
          }

          if (this.__lastPosition !== position) {
            this.$refs.content.style.transform = "translateX(" + position + "px)";
            this.__lastPosition = position;
          }
        }
      },

      __applyBackdrop: function __applyBackdrop (x, retry) {
        var this$1 = this;

        if (this.$refs.backdrop !== void 0) {
          this.$refs.backdrop.style.backgroundColor =
            this.lastBackdropBg = "rgba(0,0,0," + (x * 0.4) + ")";
        }
        else {
          // rendered nodes might not have
          // picked up this.showing change yet,
          // so we need one retry
          retry !== true && this.$nextTick(function () {
            this$1.__applyBackdrop(x, true);
          });
        }
      },

      __setScrollable: function __setScrollable (v) {
        var action = v === true
          ? 'remove'
          : (this.layout.container !== true ? 'add' : '');

        action !== '' && document.body.classList[action]('q-body--drawer-toggle');
      },

      __animateMini: function __animateMini () {
        var this$1 = this;

        if (this.timerMini !== void 0) {
          clearTimeout(this.timerMini);
        }
        else if (this.$el !== void 0) {
          this.$el.classList.add('q-drawer--mini-animate');
        }
        this.timerMini = setTimeout(function () {
          this$1.$el !== void 0 && this$1.$el.classList.remove('q-drawer--mini-animate');
          this$1.timerMini = void 0;
        }, 150);
      },

      __openByTouch: function __openByTouch (evt) {
        if (this.showing !== false) {
          // some browsers might capture and trigger this
          // even if Drawer has just been opened (but animation is still pending)
          return
        }

        var
          width = this.size,
          position = between(evt.distance.x, 0, width);

        if (evt.isFinal === true) {
          var
            el = this.$refs.content,
            opened = position >= Math.min(75, width);

          el.classList.remove('no-transition');

          if (opened === true) {
            this.show();
          }
          else {
            this.layout.__animate();
            this.__applyBackdrop(0);
            this.__applyPosition(this.stateDirection * width);
            el.classList.remove('q-drawer--delimiter');
          }

          return
        }

        this.__applyPosition(
          (this.$q.lang.rtl === true ? this.rightSide !== true : this.rightSide)
            ? Math.max(width - position, 0)
            : Math.min(0, position - width)
        );
        this.__applyBackdrop(
          between(position / width, 0, 1)
        );

        if (evt.isFirst === true) {
          var el$1 = this.$refs.content;
          el$1.classList.add('no-transition');
          el$1.classList.add('q-drawer--delimiter');
        }
      },

      __closeByTouch: function __closeByTouch (evt) {
        if (this.showing !== true) {
          // some browsers might capture and trigger this
          // even if Drawer has just been closed (but animation is still pending)
          return
        }

        var
          width = this.size,
          dir = evt.direction === this.side,
          position = (this.$q.lang.rtl === true ? dir !== true : dir)
            ? between(evt.distance.x, 0, width)
            : 0;

        if (evt.isFinal === true) {
          var opened = Math.abs(position) < Math.min(75, width);
          this.$refs.content.classList.remove('no-transition');

          if (opened === true) {
            this.layout.__animate();
            this.__applyBackdrop(1);
            this.__applyPosition(0);
          }
          else {
            this.hide();
          }

          return
        }

        this.__applyPosition(this.stateDirection * position);
        this.__applyBackdrop(between(1 - position / width, 0, 1));

        if (evt.isFirst === true) {
          this.$refs.content.classList.add('no-transition');
        }
      },

      __show: function __show (evt, noEvent) {
        var this$1 = this;

        this.__addHistory();

        evt !== false && this.layout.__animate();
        this.__applyPosition(0);

        if (this.belowBreakpoint === true) {
          var otherSide = this.layout.instances[this.otherSide];
          if (otherSide !== void 0 && otherSide.belowBreakpoint === true) {
            otherSide.hide(false);
          }

          this.__applyBackdrop(1);
          this.layout.container !== true && this.__preventScroll(true);
        }
        else {
          this.__applyBackdrop(0);
          evt !== false && this.__setScrollable(false);
        }

        this.__setTimeout(function () {
          evt !== false && this$1.__setScrollable(true);
          noEvent !== true && this$1.$emit('show', evt);
        }, duration);
      },

      __hide: function __hide (evt, noEvent) {
        var this$1 = this;

        this.__removeHistory();

        evt !== false && this.layout.__animate();

        this.__applyBackdrop(0);
        this.__applyPosition(this.stateDirection * this.size);

        this.__cleanup();

        noEvent !== true && this.__setTimeout(function () {
          this$1.$emit('hide', evt);
        }, duration);
      },

      __cleanup: function __cleanup () {
        this.__preventScroll(false);
        this.__setScrollable(true);
      },

      __update: function __update (prop, val) {
        if (this.layout[this.side][prop] !== val) {
          this.layout[this.side][prop] = val;
        }
      },

      __updateLocal: function __updateLocal (prop, val) {
        if (this[prop] !== val) {
          this[prop] = val;
        }
      },

      __updateSizeOnLayout: function __updateSizeOnLayout (miniToOverlay, size) {
        this.__update('size', miniToOverlay === true ? this.miniWidth : size);
      }
    },

    created: function created () {
      this.layout.instances[this.side] = this;
      this.__updateSizeOnLayout(this.miniToOverlay, this.size);
      this.__update('space', this.onLayout);
      this.__update('offset', this.offset);

      if (
        this.showIfAbove === true &&
        this.value !== true &&
        this.showing === true &&
        this.$listeners.input !== void 0
      ) {
        this.$emit('input', true);
      }
    },

    mounted: function mounted () {
      var this$1 = this;

      this.$emit('on-layout', this.onLayout);
      this.$emit('mini-state', this.isMini);

      var fn = function () {
        var action = this$1.showing === true ? 'show' : 'hide';
        this$1[("__" + action)](false, true);
      };

      if (this.layout.totalWidth !== 0) {
        fn();
        return
      }

      this.watcher = this.$watch('layout.totalWidth', function () {
        this$1.watcher();
        this$1.watcher = void 0;

        if (this$1.showing === false && this$1.showIfAbove === true && this$1.belowBreakpoint === false) {
          this$1.show(false);
        }
        else {
          fn();
        }
      });
    },

    beforeDestroy: function beforeDestroy () {
      this.watcher !== void 0 && this.watcher();
      clearTimeout(this.timerMini);

      this.showing === true && this.__cleanup();

      if (this.layout.instances[this.side] === this) {
        this.layout.instances[this.side] = void 0;
        this.__update('size', 0);
        this.__update('offset', 0);
        this.__update('space', false);
      }
    },

    render: function render (h) {
      var child = [];

      if (this.belowBreakpoint === true) {
        this.noSwipeOpen !== true && child.push(
          h('div', {
            staticClass: ("q-drawer__opener fixed-" + (this.side)),
            directives: this.openDirective
          })
        );

        child.push(
          h('div', {
            ref: 'backdrop',
            staticClass: 'fullscreen q-drawer__backdrop',
            class: this.backdropClass,
            style: this.lastBackdropBg !== void 0
              ? { backgroundColor: this.lastBackdropBg }
              : null,
            on: cache(this, 'bkdrop', { click: this.hide }),
            directives: this.backdropCloseDirective
          })
        );
      }

      var content = [
        h('div', {
          staticClass: 'q-drawer__content fit ' + (this.layout.container === true ? 'overflow-auto' : 'scroll'),
          class: this.contentClass,
          style: this.contentStyle
        }, this.isMini === true && this.$scopedSlots.mini !== void 0
          ? this.$scopedSlots.mini()
          : slot(this, 'default')
        )
      ];

      if (this.elevated === true && this.showing === true) {
        content.push(
          h('div', {
            staticClass: 'q-layout__shadow absolute-full overflow-hidden no-pointer-events'
          })
        );
      }

      child.push(
        h('aside', {
          ref: 'content',
          staticClass: "q-drawer",
          class: this.classes,
          style: this.style,
          on: this.onNativeEvents,
          directives: this.belowBreakpoint === true
            ? this.contentCloseDirective
            : void 0
        }, content)
      );

      return h('div', { staticClass: 'q-drawer-container' }, child)
    }
  });

  var ValidateMixin = {
    props: {
      value: {},

      error: {
        type: Boolean,
        default: null
      },
      errorMessage: String,
      noErrorIcon: Boolean,

      rules: Array,
      lazyRules: Boolean
    },

    data: function data () {
      return {
        isDirty: null,
        innerError: false,
        innerErrorMessage: void 0
      }
    },

    watch: {
      value: function value (v) {
        if (this.rules === void 0) {
          return
        }
        if (this.lazyRules === true && this.isDirty !== true) {
          return
        }

        this.validate(v);
      },

      focused: function focused (focused$1) {
        if (focused$1 === true) {
          this.__initDirty();
        }
        else {
          this.__triggerValidation();
        }
      }
    },

    computed: {
      hasError: function hasError () {
        return this.error === true || this.innerError === true
      },

      computedErrorMessage: function computedErrorMessage () {
        return typeof this.errorMessage === 'string' && this.errorMessage.length > 0
          ? this.errorMessage
          : this.innerErrorMessage
      }
    },

    mounted: function mounted () {
      this.validateIndex = 0;
      if (this.focused === void 0) {
        this.$el.addEventListener('focusin', this.__initDirty);
        this.$el.addEventListener('focusout', this.__triggerValidation);
      }
    },

    beforeDestroy: function beforeDestroy () {
      if (this.focused === void 0) {
        this.$el.removeEventListener('focusin', this.__initDirty);
        this.$el.removeEventListener('focusout', this.__triggerValidation);
      }
    },

    methods: {
      resetValidation: function resetValidation () {
        this.validateIndex++;
        this.innerLoading = false;
        this.isDirty = null;
        this.innerError = false;
        this.innerErrorMessage = void 0;
      },

      /*
       * Return value
       *   - true (validation succeeded)
       *   - false (validation failed)
       *   - Promise (pending async validation)
       */
      validate: function validate (val) {
        var this$1 = this;
        if ( val === void 0 ) val = this.value;

        if (!this.rules || this.rules.length === 0) {
          return true
        }

        this.validateIndex++;

        if (this.innerLoading !== true && this.lazyRules !== true) {
          this.isDirty = true;
        }

        var update = function (err, msg) {
          if (this$1.innerError !== err) {
            this$1.innerError = err;
          }

          var m = msg || void 0;
          if (this$1.innerErrorMessage !== m) {
            this$1.innerErrorMessage = m;
          }

          if (this$1.innerLoading !== false) {
            this$1.innerLoading = false;
          }
        };

        var promises = [];

        for (var i = 0; i < this.rules.length; i++) {
          var rule = this.rules[i];
          var res = (void 0);

          if (typeof rule === 'function') {
            res = rule(val);
          }
          else if (typeof rule === 'string' && testPattern[rule] !== void 0) {
            res = testPattern[rule](val);
          }

          if (res === false || typeof res === 'string') {
            update(true, res);
            return false
          }
          else if (res !== true && res !== void 0) {
            promises.push(res);
          }
        }

        if (promises.length === 0) {
          update(false);
          return true
        }

        if (this.innerLoading !== true) {
          this.innerLoading = true;
        }

        var index = this.validateIndex;

        return Promise.all(promises).then(
          function (res) {
            if (index !== this$1.validateIndex) {
              return true
            }

            if (res === void 0 || Array.isArray(res) === false || res.length === 0) {
              update(false);
              return true
            }

            var msg = res.find(function (r) { return r === false || typeof r === 'string'; });
            update(msg !== void 0, msg);
            return msg === void 0
          },
          function (e) {
            if (index === this$1.validateIndex) {
              console.error(e);
              update(true);
              return false
            }

            return true
          }
        )
      },

      __initDirty: function __initDirty () {
        if (this.isDirty === null) {
          this.isDirty = false;
        }
      },

      __triggerValidation: function __triggerValidation () {
        if (this.isDirty === false && this.rules !== void 0) {
          this.isDirty = true;
          this.validate(this.value);
        }
      }
    }
  };

  /**
   * Based on the work of https://github.com/jchook/uuid-random
   */

  var
    buf,
    bufIdx = 0,
    hexBytes = new Array(256);

  // Pre-calculate toString(16) for speed
  for (var i = 0; i < 256; i++) {
    hexBytes[i] = (i + 0x100).toString(16).substr(1);
  }

  // Use best available PRNG
  var randomBytes = (function () {
    // Node & Browser support
    var lib = typeof crypto !== 'undefined'
      ? crypto
      : (
        typeof window !== 'undefined'
          ? window.msCrypto // IE11
          : void 0
      );

    if (lib !== void 0) {
      if (lib.randomBytes !== void 0) {
        return lib.randomBytes
      }
      if (lib.getRandomValues !== void 0) {
        return function (n) {
          var bytes = new Uint8Array(n);
          lib.getRandomValues(bytes);
          return bytes
        }
      }
    }

    return function (n) {
      var r = [];
      for (var i = n; i > 0; i--) {
        r.push(Math.floor(Math.random() * 256));
      }
      return r
    }
  })();

  // Buffer random numbers for speed
  // Reduce memory usage by decreasing this number (min 16)
  // or improve speed by increasing this number (try 16384)
  var BUFFER_SIZE = 4096;

  function uid$2 () {
    // Buffer some random bytes for speed
    if (buf === void 0 || (bufIdx + 16 > BUFFER_SIZE)) {
      bufIdx = 0;
      buf = randomBytes(BUFFER_SIZE);
    }

    var b = buf.slice(bufIdx, (bufIdx += 16));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;

    return hexBytes[b[0]] + hexBytes[b[1]] +
      hexBytes[b[2]] + hexBytes[b[3]] + '-' +
      hexBytes[b[4]] + hexBytes[b[5]] + '-' +
      hexBytes[b[6]] + hexBytes[b[7]] + '-' +
      hexBytes[b[8]] + hexBytes[b[9]] + '-' +
      hexBytes[b[10]] + hexBytes[b[11]] +
      hexBytes[b[12]] + hexBytes[b[13]] +
      hexBytes[b[14]] + hexBytes[b[15]]
  }

  function getTargetUid (val) {
    return val === void 0 ? ("f_" + (uid$2())) : val
  }

  var QField = Vue.extend({
    name: 'QField',

    mixins: [ DarkMixin, ValidateMixin ],

    inheritAttrs: false,

    props: {
      label: String,
      stackLabel: Boolean,
      hint: String,
      hideHint: Boolean,
      prefix: String,
      suffix: String,

      labelColor: String,
      color: String,
      bgColor: String,

      filled: Boolean,
      outlined: Boolean,
      borderless: Boolean,
      standout: [Boolean, String],

      square: Boolean,

      loading: Boolean,

      bottomSlots: Boolean,
      hideBottomSpace: Boolean,

      rounded: Boolean,
      dense: Boolean,
      itemAligned: Boolean,

      counter: Boolean,

      clearable: Boolean,
      clearIcon: String,

      disable: Boolean,
      readonly: Boolean,

      autofocus: Boolean,

      for: String,

      maxlength: [Number, String],
      maxValues: [Number, String] // private, do not add to JSON; internally needed by QSelect
    },

    data: function data () {
      return {
        focused: false,
        targetUid: getTargetUid(this.for),

        // used internally by validation for QInput
        // or menu handling for QSelect
        innerLoading: false
      }
    },

    watch: {
      for: function for$1 (val) {
        // don't transform targetUid into a computed
        // prop as it will break SSR
        this.targetUid = getTargetUid(val);
      }
    },

    computed: {
      editable: function editable () {
        return this.disable !== true && this.readonly !== true
      },

      hasValue: function hasValue () {
        var value = this.__getControl === void 0 ? this.value : this.innerValue;

        return value !== void 0 &&
          value !== null &&
          ('' + value).length > 0
      },

      computedCounter: function computedCounter () {
        if (this.counter !== false) {
          var len = typeof this.value === 'string' || typeof this.value === 'number'
            ? ('' + this.value).length
            : (Array.isArray(this.value) === true ? this.value.length : 0);

          var max = this.maxlength !== void 0
            ? this.maxlength
            : this.maxValues;

          return len + (max !== void 0 ? ' / ' + max : '')
        }
      },

      floatingLabel: function floatingLabel () {
        return this.stackLabel === true ||
          this.focused === true ||
          (
            this.inputValue !== void 0 && this.hideSelected === true
              ? this.inputValue.length > 0
              : this.hasValue === true
          ) ||
          (
            this.displayValue !== void 0 &&
            this.displayValue !== null &&
            ('' + this.displayValue).length > 0
          )
      },

      shouldRenderBottom: function shouldRenderBottom () {
        return this.bottomSlots === true ||
          this.hint !== void 0 ||
          this.rules !== void 0 ||
          this.counter === true ||
          this.error !== null
      },

      classes: function classes () {
        var obj;

        return ( obj = {}, obj[this.fieldClass] = this.fieldClass !== void 0, obj[("q-field--" + (this.styleType))] = true, obj['q-field--rounded'] = this.rounded, obj['q-field--square'] = this.square, obj['q-field--focused'] = this.focused === true || this.hasError === true, obj['q-field--float'] = this.floatingLabel, obj['q-field--labeled'] = this.label !== void 0, obj['q-field--dense'] = this.dense, obj['q-field--item-aligned q-item-type'] = this.itemAligned, obj['q-field--dark'] = this.isDark, obj['q-field--auto-height'] = this.__getControl === void 0, obj['q-field--with-bottom'] = this.hideBottomSpace !== true && this.shouldRenderBottom === true, obj['q-field--error'] = this.hasError, obj['q-field--readonly'] = this.readonly === true && this.disable !== true, obj['q-field--disabled'] = this.disable, obj )
      },

      styleType: function styleType () {
        if (this.filled === true) { return 'filled' }
        if (this.outlined === true) { return 'outlined' }
        if (this.borderless === true) { return 'borderless' }
        if (this.standout) { return 'standout' }
        return 'standard'
      },

      contentClass: function contentClass () {
        var cls = [];

        if (this.hasError === true) {
          cls.push('text-negative');
        }
        else if (typeof this.standout === 'string' && this.standout.length > 0 && this.focused === true) {
          return this.standout
        }
        else if (this.color !== void 0) {
          cls.push('text-' + this.color);
        }

        if (this.bgColor !== void 0) {
          cls.push(("bg-" + (this.bgColor)));
        }

        return cls
      },

      labelClass: function labelClass () {
        if (
          this.labelColor !== void 0 &&
          this.hasError !== true
        ) {
          return 'text-' + this.labelColor
        }
      },

      controlSlotScope: function controlSlotScope () {
        return {
          id: this.targetUid,
          field: this.$el,
          editable: this.editable,
          focused: this.focused,
          floatingLabel: this.floatingLabel,
          value: this.value,
          emitValue: this.__emitValue
        }
      },

      attrs: function attrs () {
        var attrs = {
          for: this.targetUid
        };

        if (this.disable === true) {
          attrs['aria-disabled'] = '';
        }
        else if (this.readonly === true) {
          attrs['aria-readonly'] = '';
        }

        return attrs
      }
    },

    methods: {
      focus: function focus () {
        if (this.showPopup !== void 0 && this.hasDialog === true) {
          this.showPopup();
          return
        }

        this.__focus();
      },

      blur: function blur () {
        var el = document.activeElement;
        // IE can have null document.activeElement
        if (el !== null && this.$el.contains(el)) {
          el.blur();
        }
      },

      __focus: function __focus () {
        var el = document.activeElement;
        var target = this.$refs.target;
        // IE can have null document.activeElement
        if (target !== void 0 && (el === null || el.id !== this.targetUid)) {
          target.hasAttribute('tabindex') === true || (target = target.querySelector('[tabindex]'));
          target !== null && target !== el && target.focus();
        }
      },

      __getContent: function __getContent (h) {
        var node = [];

        this.$scopedSlots.prepend !== void 0 && node.push(
          h('div', {
            staticClass: 'q-field__prepend q-field__marginal row no-wrap items-center',
            key: 'prepend',
            on: this.slotsEvents
          }, this.$scopedSlots.prepend())
        );

        node.push(
          h('div', {
            staticClass: 'q-field__control-container col relative-position row no-wrap q-anchor--skip'
          }, this.__getControlContainer(h))
        );

        this.$scopedSlots.append !== void 0 && node.push(
          h('div', {
            staticClass: 'q-field__append q-field__marginal row no-wrap items-center',
            key: 'append',
            on: this.slotsEvents
          }, this.$scopedSlots.append())
        );

        this.hasError === true && this.noErrorIcon === false && node.push(
          this.__getInnerAppendNode(h, 'error', [
            h(QIcon, { props: { name: this.$q.iconSet.field.error, color: 'negative' } })
          ])
        );

        if (this.loading === true || this.innerLoading === true) {
          node.push(
            this.__getInnerAppendNode(
              h,
              'inner-loading-append',
              this.$scopedSlots.loading !== void 0
                ? this.$scopedSlots.loading()
                : [ h(QSpinner, { props: { color: this.color } }) ]
            )
          );
        }
        else if (this.clearable === true && this.hasValue === true && this.editable === true) {
          node.push(
            this.__getInnerAppendNode(h, 'inner-clearable-append', [
              h(QIcon, {
                staticClass: 'cursor-pointer',
                props: { name: this.clearIcon || this.$q.iconSet.field.clear },
                on: this.clearableEvents
              })
            ])
          );
        }

        this.__getInnerAppend !== void 0 && node.push(
          this.__getInnerAppendNode(h, 'inner-append', this.__getInnerAppend(h))
        );

        this.__getControlChild !== void 0 && node.push(
          this.__getControlChild(h)
        );

        return node
      },

      __getControlContainer: function __getControlContainer (h) {
        var node = [];

        this.prefix !== void 0 && this.prefix !== null && node.push(
          h('div', {
            staticClass: 'q-field__prefix no-pointer-events row items-center'
          }, [ this.prefix ])
        );

        if (this.__getControl !== void 0) {
          node.push(
            this.__getControl(h)
          );
        }
        // internal usage only:
        else if (this.$scopedSlots.rawControl !== void 0) {
          node.push(this.$scopedSlots.rawControl());
        }
        else if (this.$scopedSlots.control !== void 0) {
          node.push(
            h('div', {
              ref: 'target',
              staticClass: 'q-field__native row',
              attrs: Object.assign({}, this.$attrs,
                {'data-autofocus': this.autofocus})
            }, this.$scopedSlots.control(this.controlSlotScope))
          );
        }

        this.label !== void 0 && node.push(
          h('div', {
            staticClass: 'q-field__label no-pointer-events absolute ellipsis',
            class: this.labelClass
          }, [ this.label ])
        );

        this.suffix !== void 0 && this.suffix !== null && node.push(
          h('div', {
            staticClass: 'q-field__suffix no-pointer-events row items-center'
          }, [ this.suffix ])
        );

        return node.concat(
          this.__getDefaultSlot !== void 0
            ? this.__getDefaultSlot(h)
            : slot(this, 'default')
        )
      },

      __getBottom: function __getBottom (h) {
        var msg, key;

        if (this.hasError === true) {
          if (this.computedErrorMessage !== void 0) {
            msg = [ h('div', [ this.computedErrorMessage ]) ];
            key = this.computedErrorMessage;
          }
          else {
            msg = slot(this, 'error');
            key = 'q--slot-error';
          }
        }
        else if (this.hideHint !== true || this.focused === true) {
          if (this.hint !== void 0) {
            msg = [ h('div', [ this.hint ]) ];
            key = this.hint;
          }
          else {
            msg = slot(this, 'hint');
            key = 'q--slot-hint';
          }
        }

        var hasCounter = this.counter === true || this.$scopedSlots.counter !== void 0;

        if (this.hideBottomSpace === true && hasCounter === false && msg === void 0) {
          return
        }

        var main = h('div', {
          key: key,
          staticClass: 'q-field__messages col'
        }, msg);

        return h('div', {
          staticClass: 'q-field__bottom row items-start q-field__bottom--' +
            (this.hideBottomSpace !== true ? 'animated' : 'stale')
        }, [
          this.hideBottomSpace === true
            ? main
            : h('transition', { props: { name: 'q-transition--field-message' } }, [
              main
            ]),

          hasCounter === true
            ? h('div', {
              staticClass: 'q-field__counter'
            }, this.$scopedSlots.counter !== void 0 ? this.$scopedSlots.counter() : [ this.computedCounter ])
            : null
        ])
      },

      __getInnerAppendNode: function __getInnerAppendNode (h, key, content) {
        return content === null ? null : h('div', {
          staticClass: 'q-field__append q-field__marginal row no-wrap items-center q-anchor--skip',
          key: key
        }, content)
      },

      __onControlPopupShow: function __onControlPopupShow (e) {
        e !== void 0 && stop(e);
        this.$emit('popup-show', e);
        this.hasPopupOpen = true;
        this.__onControlFocusin(e);
      },

      __onControlPopupHide: function __onControlPopupHide (e) {
        e !== void 0 && stop(e);
        this.$emit('popup-hide', e);
        this.hasPopupOpen = false;
        this.__onControlFocusout(e);
      },

      __onControlFocusin: function __onControlFocusin (e) {
        if (this.editable === true && this.focused === false) {
          this.focused = true;
          this.$emit('focus', e);
        }
      },

      __onControlFocusout: function __onControlFocusout (e, then) {
        var this$1 = this;

        clearTimeout(this.focusoutTimer);
        this.focusoutTimer = setTimeout(function () {
          if (
            document.hasFocus() === true && (
              this$1.hasPopupOpen === true ||
              this$1.$refs === void 0 ||
              this$1.$refs.control === void 0 ||
              this$1.$refs.control.contains(document.activeElement) !== false
            )
          ) {
            return
          }

          if (this$1.focused === true) {
            this$1.focused = false;
            this$1.$emit('blur', e);
          }

          then !== void 0 && then();
        });
      },

      __clearValue: function __clearValue (e) {
        stop(e);
        if (this.type === 'file') {
          // do not let focus be triggered
          // as it will make the native file dialog
          // appear for another selection
          prevent(e);
          this.$refs.input.value = null;
        }
        this.$emit('input', null);
        this.$emit('clear', this.value);
      },

      __emitValue: function __emitValue (value) {
        this.$emit('input', value);
      }
    },

    render: function render (h) {
      this.__onPreRender !== void 0 && this.__onPreRender();
      this.__onPostRender !== void 0 && this.$nextTick(this.__onPostRender);

      return h('label', {
        staticClass: 'q-field row no-wrap items-start',
        class: this.classes,
        attrs: this.attrs
      }, [
        this.$scopedSlots.before !== void 0 ? h('div', {
          staticClass: 'q-field__before q-field__marginal row no-wrap items-center',
          on: this.slotsEvents
        }, this.$scopedSlots.before()) : null,

        h('div', {
          staticClass: 'q-field__inner relative-position col self-stretch column justify-center'
        }, [
          h('div', {
            ref: 'control',
            staticClass: 'q-field__control relative-position row no-wrap',
            class: this.contentClass,
            attrs: { tabindex: -1 },
            on: this.controlEvents
          }, this.__getContent(h)),

          this.shouldRenderBottom === true
            ? this.__getBottom(h)
            : null
        ]),

        this.$scopedSlots.after !== void 0 ? h('div', {
          staticClass: 'q-field__after q-field__marginal row no-wrap items-center',
          on: this.slotsEvents
        }, this.$scopedSlots.after()) : null
      ])
    },

    created: function created () {
      this.__onPreRender !== void 0 && this.__onPreRender();

      this.slotsEvents = { click: prevent };

      this.clearableEvents = { click: this.__clearValue };

      this.controlEvents = this.__getControlEvents !== void 0
        ? this.__getControlEvents()
        : {
          focusin: this.__onControlFocusin,
          focusout: this.__onControlFocusout,
          'popup-show': this.__onControlPopupShow,
          'popup-hide': this.__onControlPopupHide
        };
    },

    mounted: function mounted () {
      if (fromSSR === true && this.for === void 0) {
        this.targetUid = getTargetUid();
      }

      this.autofocus === true && this.focus();
    },

    beforeDestroy: function beforeDestroy () {
      clearTimeout(this.focusoutTimer);
    }
  });

  var FileMixin = {
    props: {
      multiple: Boolean,
      accept: String,
      maxFileSize: Number,
      maxTotalSize: Number,
      filter: Function
    },

    computed: {
      extensions: function extensions () {
        if (this.accept !== void 0) {
          return this.accept.split(',').map(function (ext) {
            ext = ext.trim();
            // support "image/*"
            if (ext.endsWith('/*')) {
              ext = ext.slice(0, ext.length - 1);
            }
            return ext
          })
        }
      }
    },

    methods: {
      pickFiles: function pickFiles (e) {
        if (this.editable === true) {
          var input = this.__getFileInput();
          input && input.click(e);
        }
      },

      addFiles: function addFiles (files) {
        if (this.editable && files) {
          this.__addFiles(null, files);
        }
      },

      __processFiles: function __processFiles (e, files) {
        var this$1 = this;

        files = Array.from(files || e.target.files);

        // filter file types
        if (this.accept !== void 0) {
          files = files.filter(function (file) {
            return this$1.extensions.some(function (ext) { return (
              file.type.toUpperCase().startsWith(ext.toUpperCase()) ||
              file.name.toUpperCase().endsWith(ext.toUpperCase())
            ); })
          });
          if (files.length === 0) { return }
        }

        // filter max file size
        if (this.maxFileSize !== void 0) {
          files = files.filter(function (file) { return file.size <= this$1.maxFileSize; });
          if (files.length === 0) { return }
        }

        // Cordova/iOS allows selecting multiple files even when the
        // multiple attribute is not specified. We also normalize drag'n'dropped
        // files here:
        if (this.multiple !== true) {
          files = [ files[0] ];
        }

        if (this.maxTotalSize !== void 0) {
          var size = 0;
          for (var i = 0; i < files.length; i++) {
            size += files[i].size;
            if (size > this.maxTotalSize) {
              if (i > 0) {
                files = files.slice(0, i);
                break
              }
              else {
                return
              }
            }
          }
          if (files.length === 0) { return }
        }

        // do we have custom filter function?
        if (typeof this.filter === 'function') {
          files = this.filter(files);
        }

        if (files.length > 0) {
          return files
        }
      },

      __onDragOver: function __onDragOver (e) {
        stopAndPrevent(e);
        this.dnd = true;
      },

      __onDragLeave: function __onDragLeave (e) {
        stopAndPrevent(e);
        this.dnd = false;
      },

      __onDrop: function __onDrop (e) {
        stopAndPrevent(e);
        var files = e.dataTransfer.files;

        if (files.length > 0) {
          this.__addFiles(null, files);
        }

        this.dnd = false;
      },

      __getDnd: function __getDnd (h, type) {
        if (this.dnd === true) {
          return h('div', {
            staticClass: ("q-" + type + "__dnd absolute-full"),
            on: cache(this, 'dnd', {
              dragenter: stopAndPrevent,
              dragover: stopAndPrevent,
              dragleave: this.__onDragLeave,
              drop: this.__onDrop
            })
          })
        }
      }
    }
  };

  var FileValueMixin = {
    computed: {
      formDomProps: function formDomProps () {
        if (this.type !== 'file') {
          return
        }

        try {
          var dt = 'DataTransfer' in window
            ? new DataTransfer()
            : ('ClipboardEvent' in window
              ? new ClipboardEvent('').clipboardData
              : void 0
            );

          if (Object(this.value) === this.value) {
            ('length' in this.value
              ? Array.from(this.value)
              : [ this.value ]
            ).forEach(function (file) {
              dt.items.add(file);
            });
          }

          return {
            files: dt.files
          }
        }
        catch (e) {
          return {
            files: void 0
          }
        }
      }
    }
  };

  // leave NAMED_MASKS at top of file (code referenced from docs)
  var NAMED_MASKS = {
    date: '####/##/##',
    datetime: '####/##/## ##:##',
    time: '##:##',
    fulltime: '##:##:##',
    phone: '(###) ### - ####',
    card: '#### #### #### ####'
  };

  var TOKENS = {
    '#': { pattern: '[\\d]', negate: '[^\\d]' },

    S: { pattern: '[a-zA-Z]', negate: '[^a-zA-Z]' },
    N: { pattern: '[0-9a-zA-Z]', negate: '[^0-9a-zA-Z]' },

    A: { pattern: '[a-zA-Z]', negate: '[^a-zA-Z]', transform: function (v) { return v.toLocaleUpperCase(); } },
    a: { pattern: '[a-zA-Z]', negate: '[^a-zA-Z]', transform: function (v) { return v.toLocaleLowerCase(); } },

    X: { pattern: '[0-9a-zA-Z]', negate: '[^0-9a-zA-Z]', transform: function (v) { return v.toLocaleUpperCase(); } },
    x: { pattern: '[0-9a-zA-Z]', negate: '[^0-9a-zA-Z]', transform: function (v) { return v.toLocaleLowerCase(); } }
  };

  var KEYS = Object.keys(TOKENS);
  KEYS.forEach(function (key) {
    TOKENS[key].regex = new RegExp(TOKENS[key].pattern);
  });

  var
    tokenRegexMask = new RegExp('\\\\([^.*+?^${}()|([\\]])|([.*+?^${}()|[\\]])|([' + KEYS.join('') + '])|(.)', 'g'),
    escRegex = /[.*+?^${}()|[\]\\]/g;

  var MARKER = String.fromCharCode(1);

  var MaskMixin = {
    props: {
      mask: String,
      reverseFillMask: Boolean,
      fillMask: [Boolean, String],
      unmaskedValue: Boolean
    },

    watch: {
      type: function type () {
        this.__updateMaskInternals();
      },

      mask: function mask (v) {
        if (v !== void 0) {
          this.__updateMaskValue(this.innerValue, true);
        }
        else {
          var val = this.__unmask(this.innerValue);
          this.__updateMaskInternals();
          this.value !== val && this.$emit('input', val);
        }
      },

      fillMask: function fillMask () {
        this.hasMask === true && this.__updateMaskValue(this.innerValue, true);
      },

      reverseFillMask: function reverseFillMask () {
        this.hasMask === true && this.__updateMaskValue(this.innerValue, true);
      },

      unmaskedValue: function unmaskedValue () {
        this.hasMask === true && this.__updateMaskValue(this.innerValue);
      }
    },

    methods: {
      __getInitialMaskedValue: function __getInitialMaskedValue () {
        this.__updateMaskInternals();

        if (this.hasMask === true) {
          var masked = this.__mask(this.__unmask(this.value));

          return this.fillMask !== false
            ? this.__fillWithMask(masked)
            : masked
        }

        return this.value
      },

      __getPaddedMaskMarked: function __getPaddedMaskMarked (size) {
        if (size < this.maskMarked.length) {
          return this.maskMarked.slice(-size)
        }

        var
          maskMarked = this.maskMarked,
          padPos = maskMarked.indexOf(MARKER),
          pad = '';

        if (padPos > -1) {
          for (var i = size - maskMarked.length; i > 0; i--) {
            pad += MARKER;
          }

          maskMarked = maskMarked.slice(0, padPos) + pad + maskMarked.slice(padPos);
        }

        return maskMarked
      },

      __updateMaskInternals: function __updateMaskInternals () {
        var this$1 = this;

        this.hasMask = this.mask !== void 0 &&
          this.mask.length > 0 &&
          ['text', 'search', 'url', 'tel', 'password'].includes(this.type);

        if (this.hasMask === false) {
          this.computedUnmask = void 0;
          this.maskMarked = '';
          this.maskReplaced = '';
          return
        }

        var
          computedMask = NAMED_MASKS[this.mask] === void 0
            ? this.mask
            : NAMED_MASKS[this.mask],
          fillChar = typeof this.fillMask === 'string' && this.fillMask.length > 0
            ? this.fillMask.slice(0, 1)
            : '_',
          fillCharEscaped = fillChar.replace(escRegex, '\\$&'),
          unmask = [],
          extract = [],
          mask = [];

        var
          firstMatch = this.reverseFillMask === true,
          unmaskChar = '',
          negateChar = '';

        computedMask.replace(tokenRegexMask, function (_, char1, esc, token, char2) {
          if (token !== void 0) {
            var c = TOKENS[token];
            mask.push(c);
            negateChar = c.negate;
            if (firstMatch === true) {
              extract.push('(?:' + negateChar + '+)?(' + c.pattern + '+)?(?:' + negateChar + '+)?(' + c.pattern + '+)?');
              firstMatch = false;
            }
            extract.push('(?:' + negateChar + '+)?(' + c.pattern + ')?');
          }
          else if (esc !== void 0) {
            unmaskChar = '\\' + (esc === '\\' ? '' : esc);
            mask.push(esc);
            unmask.push('([^' + unmaskChar + ']+)?' + unmaskChar + '?');
          }
          else {
            var c$1 = char1 !== void 0 ? char1 : char2;
            unmaskChar = c$1 === '\\' ? '\\\\\\\\' : c$1.replace(escRegex, '\\\\$&');
            mask.push(c$1);
            unmask.push('([^' + unmaskChar + ']+)?' + unmaskChar + '?');
          }
        });

        var
          unmaskMatcher = new RegExp(
            '^' +
            unmask.join('') +
            '(' + (unmaskChar === '' ? '.' : '[^' + unmaskChar + ']') + '+)?' +
            '$'
          ),
          extractLast = extract.length - 1,
          extractMatcher = extract.map(function (re, index) {
            if (index === 0 && this$1.reverseFillMask === true) {
              return new RegExp('^' + fillCharEscaped + '*' + re)
            }
            else if (index === extractLast) {
              return new RegExp(
                '^' + re +
                '(' + (negateChar === '' ? '.' : negateChar) + '+)?' +
                (this$1.reverseFillMask === true ? '$' : fillCharEscaped + '*')
              )
            }

            return new RegExp('^' + re)
          });

        this.computedMask = mask;
        this.computedUnmask = function (val) {
          var unmaskMatch = unmaskMatcher.exec(val);
          if (unmaskMatch !== null) {
            val = unmaskMatch.slice(1).join('');
          }

          var
            extractMatch = [],
            extractMatcherLength = extractMatcher.length;

          for (var i = 0, str = val; i < extractMatcherLength; i++) {
            var m = extractMatcher[i].exec(str);

            if (m === null) {
              break
            }

            str = str.slice(m.shift().length);
            extractMatch.push.apply(extractMatch, m);
          }
          if (extractMatch.length > 0) {
            return extractMatch.join('')
          }

          return val
        };
        this.maskMarked = mask.map(function (v) { return typeof v === 'string' ? v : MARKER; }).join('');
        this.maskReplaced = this.maskMarked.split(MARKER).join(fillChar);
      },

      __updateMaskValue: function __updateMaskValue (rawVal, updateMaskInternals, inputType) {
        var this$1 = this;

        var
          inp = this.$refs.input,
          end = inp.selectionEnd,
          endReverse = inp.value.length - end,
          unmasked = this.__unmask(rawVal);

        // Update here so unmask uses the original fillChar
        updateMaskInternals === true && this.__updateMaskInternals();

        var
          preMasked = this.__mask(unmasked),
          masked = this.fillMask !== false
            ? this.__fillWithMask(preMasked)
            : preMasked,
          changed = this.innerValue !== masked;

        // We want to avoid "flickering" so we set value immediately
        inp.value !== masked && (inp.value = masked);

        changed === true && (this.innerValue = masked);

        this.$nextTick(function () {
          if (masked === this$1.maskReplaced) {
            var cursor = this$1.reverseFillMask === true ? this$1.maskReplaced.length : 0;
            inp.setSelectionRange(cursor, cursor, 'forward');

            return
          }

          if (inputType === 'insertFromPaste' && this$1.reverseFillMask !== true) {
            var cursor$1 = end - 1;
            this$1.__moveCursorRight(inp, cursor$1, cursor$1);

            return
          }

          if (['deleteContentBackward', 'deleteContentForward'].indexOf(inputType) > -1) {
            var cursor$2 = this$1.reverseFillMask === true
              ? Math.max(0, masked.length - (masked === this$1.maskReplaced ? 0 : Math.min(preMasked.length, endReverse) + 1)) + 1
              : end;
            inp.setSelectionRange(cursor$2, cursor$2, 'forward');

            return
          }

          if (this$1.reverseFillMask === true) {
            if (changed === true) {
              var cursor$3 = Math.max(0, masked.length - (masked === this$1.maskReplaced ? 0 : Math.min(preMasked.length, endReverse + 1)));
              this$1.__moveCursorRightReverse(inp, cursor$3, cursor$3);
            }
            else {
              var cursor$4 = masked.length - endReverse;
              inp.setSelectionRange(cursor$4, cursor$4, 'backward');
            }
          }
          else {
            if (changed === true) {
              var cursor$5 = Math.max(0, this$1.maskMarked.indexOf(MARKER), Math.min(preMasked.length, end) - 1);
              this$1.__moveCursorRight(inp, cursor$5, cursor$5);
            }
            else {
              var cursor$6 = end - 1;
              this$1.__moveCursorRight(inp, cursor$6, cursor$6);
            }
          }
        });

        var val = this.unmaskedValue === true
          ? this.__unmask(masked)
          : masked;

        this.value !== val && this.__emitValue(val, true);
      },

      __moveCursorForPaste: function __moveCursorForPaste (inp, start, end) {
        var preMasked = this.__mask(this.__unmask(inp.value));

        start = Math.max(0, this.maskMarked.indexOf(MARKER), Math.min(preMasked.length, start));

        inp.setSelectionRange(start, end, 'forward');
      },

      __moveCursorLeft: function __moveCursorLeft (inp, start, end, selection) {
        var noMarkBefore = this.maskMarked.slice(start - 1).indexOf(MARKER) === -1;
        var i = Math.max(0, start - 1);

        for (; i >= 0; i--) {
          if (this.maskMarked[i] === MARKER) {
            start = i;
            noMarkBefore === true && start++;
            break
          }
        }

        if (
          i < 0 &&
          this.maskMarked[start] !== void 0 &&
          this.maskMarked[start] !== MARKER
        ) {
          return this.__moveCursorRight(inp, 0, 0)
        }

        start >= 0 && inp.setSelectionRange(
          start,
          selection === true ? end : start, 'backward'
        );
      },

      __moveCursorRight: function __moveCursorRight (inp, start, end, selection) {
        var limit = inp.value.length;
        var i = Math.min(limit, end + 1);

        for (; i <= limit; i++) {
          if (this.maskMarked[i] === MARKER) {
            end = i;
            break
          }
          else if (this.maskMarked[i - 1] === MARKER) {
            end = i;
          }
        }

        if (
          i > limit &&
          this.maskMarked[end - 1] !== void 0 &&
          this.maskMarked[end - 1] !== MARKER
        ) {
          return this.__moveCursorLeft(inp, limit, limit)
        }

        inp.setSelectionRange(selection ? start : end, end, 'forward');
      },

      __moveCursorLeftReverse: function __moveCursorLeftReverse (inp, start, end, selection) {
        var
          maskMarked = this.__getPaddedMaskMarked(inp.value.length);
        var i = Math.max(0, start - 1);

        for (; i >= 0; i--) {
          if (maskMarked[i - 1] === MARKER) {
            start = i;
            break
          }
          else if (maskMarked[i] === MARKER) {
            start = i;
            if (i === 0) {
              break
            }
          }
        }

        if (
          i < 0 &&
          maskMarked[start] !== void 0 &&
          maskMarked[start] !== MARKER
        ) {
          return this.__moveCursorRightReverse(inp, 0, 0)
        }

        start >= 0 && inp.setSelectionRange(
          start,
          selection === true ? end : start, 'backward'
        );
      },

      __moveCursorRightReverse: function __moveCursorRightReverse (inp, start, end, selection) {
        var
          limit = inp.value.length,
          maskMarked = this.__getPaddedMaskMarked(limit),
          noMarkBefore = maskMarked.slice(0, end + 1).indexOf(MARKER) === -1;
        var i = Math.min(limit, end + 1);

        for (; i <= limit; i++) {
          if (maskMarked[i - 1] === MARKER) {
            end = i;
            end > 0 && noMarkBefore === true && end--;
            break
          }
        }

        if (
          i > limit &&
          maskMarked[end - 1] !== void 0 &&
          maskMarked[end - 1] !== MARKER
        ) {
          return this.__moveCursorLeftReverse(inp, limit, limit)
        }

        inp.setSelectionRange(selection === true ? start : end, end, 'forward');
      },

      __onMaskedKeydown: function __onMaskedKeydown (e) {
        if (shouldIgnoreKey(e) === true) {
          return
        }

        var
          inp = this.$refs.input,
          start = inp.selectionStart,
          end = inp.selectionEnd;

        if (e.keyCode === 37 || e.keyCode === 39) { // Left / Right
          var fn = this['__moveCursor' + (e.keyCode === 39 ? 'Right' : 'Left') + (this.reverseFillMask === true ? 'Reverse' : '')];

          e.preventDefault();
          fn(inp, start, end, e.shiftKey);
        }
        else if (
          e.keyCode === 8 && // Backspace
          this.reverseFillMask !== true &&
          start === end
        ) {
          this.__moveCursorLeft(inp, start, end, true);
        }
        else if (
          e.keyCode === 46 && // Delete
          this.reverseFillMask === true &&
          start === end
        ) {
          this.__moveCursorRightReverse(inp, start, end, true);
        }

        this.$emit('keydown', e);
      },

      __mask: function __mask (val) {
        if (val === void 0 || val === null || val === '') { return '' }

        if (this.reverseFillMask === true) {
          return this.__maskReverse(val)
        }

        var mask = this.computedMask;

        var valIndex = 0, output = '';

        for (var maskIndex = 0; maskIndex < mask.length; maskIndex++) {
          var
            valChar = val[valIndex],
            maskDef = mask[maskIndex];

          if (typeof maskDef === 'string') {
            output += maskDef;
            valChar === maskDef && valIndex++;
          }
          else if (valChar !== void 0 && maskDef.regex.test(valChar)) {
            output += maskDef.transform !== void 0
              ? maskDef.transform(valChar)
              : valChar;
            valIndex++;
          }
          else {
            return output
          }
        }

        return output
      },

      __maskReverse: function __maskReverse (val) {
        var
          mask = this.computedMask,
          firstTokenIndex = this.maskMarked.indexOf(MARKER);

        var valIndex = val.length - 1, output = '';

        for (var maskIndex = mask.length - 1; maskIndex >= 0; maskIndex--) {
          var maskDef = mask[maskIndex];

          var valChar = val[valIndex];

          if (typeof maskDef === 'string') {
            output = maskDef + output;
            valChar === maskDef && valIndex--;
          }
          else if (valChar !== void 0 && maskDef.regex.test(valChar)) {
            do {
              output = (maskDef.transform !== void 0 ? maskDef.transform(valChar) : valChar) + output;
              valIndex--;
              valChar = val[valIndex];
            // eslint-disable-next-line no-unmodified-loop-condition
            } while (firstTokenIndex === maskIndex && valChar !== void 0 && maskDef.regex.test(valChar))
          }
          else {
            return output
          }
        }

        return output
      },

      __unmask: function __unmask (val) {
        return typeof val !== 'string' || this.computedUnmask === void 0
          ? (typeof val === 'number' ? this.computedUnmask('' + val) : val)
          : this.computedUnmask(val)
      },

      __fillWithMask: function __fillWithMask (val) {
        if (this.maskReplaced.length - val.length <= 0) {
          return val
        }

        return this.reverseFillMask === true && val.length > 0
          ? this.maskReplaced.slice(0, -val.length) + val
          : val + this.maskReplaced.slice(val.length)
      }
    }
  };

  var isJapanese = /[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]/;
  var isChinese = /(?:[\u3300-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\uFE30-\uFE4F]|[\uD840-\uD868\uD86A-\uD872][\uDC00-\uDFFF]|\uD869[\uDC00-\uDEDF\uDF00-\uDFFF]|\uD873[\uDC00-\uDEAF]|\uD87E[\uDC00-\uDE1F])/;
  var isKorean = /[\u3131-\u314e\u314f-\u3163\uac00-\ud7a3]/;

  var CompositionMixin = {
    methods: {
      __onComposition: function __onComposition (e) {
        if (e.type === 'compositionend' || e.type === 'change') {
          if (e.target.composing !== true) { return }
          e.target.composing = false;
          this.__onInput(e);
        }
        else if (e.type === 'compositionupdate') {
          if (
            typeof e.data === 'string' &&
            isJapanese.test(e.data) === false &&
            isChinese.test(e.data) === false &&
            isKorean.test(e.data) === false
          ) {
            e.target.composing = false;
          }
        }
        else {
          e.target.composing = true;
        }
      }
    }
  };

  var QInput = Vue.extend({
    name: 'QInput',

    mixins: [ QField, MaskMixin, CompositionMixin, FormFieldMixin, FileValueMixin ],

    props: {
      value: { required: false },

      type: {
        type: String,
        default: 'text'
      },

      debounce: [String, Number],

      autogrow: Boolean, // makes a textarea

      inputClass: [Array, String, Object],
      inputStyle: [Array, String, Object]
    },

    watch: {
      value: function value (v) {
        if (this.hasMask === true) {
          if (this.stopValueWatcher === true) {
            this.stopValueWatcher = false;
            return
          }

          this.__updateMaskValue(v);
        }
        else if (this.innerValue !== v) {
          this.innerValue = v;

          if (
            this.type === 'number' &&
            this.hasOwnProperty('tempValue') === true
          ) {
            if (this.typedNumber === true) {
              this.typedNumber = false;
            }
            else {
              delete this.tempValue;
            }
          }
        }

        // textarea only
        this.autogrow === true && this.$nextTick(this.__adjustHeight);
      },

      autogrow: function autogrow (autogrow$1) {
        // textarea only
        if (autogrow$1 === true) {
          this.$nextTick(this.__adjustHeight);
        }
        // if it has a number of rows set respect it
        else if (this.$attrs.rows > 0 && this.$refs.input !== void 0) {
          var inp = this.$refs.input;
          inp.style.height = 'auto';
        }
      },

      dense: function dense () {
        this.autogrow === true && this.$nextTick(this.__adjustHeight);
      }
    },

    data: function data () {
      return { innerValue: this.__getInitialMaskedValue() }
    },

    computed: {
      isTextarea: function isTextarea () {
        return this.type === 'textarea' || this.autogrow === true
      },

      fieldClass: function fieldClass () {
        return "q-" + (this.isTextarea === true ? 'textarea' : 'input') +
          (this.autogrow === true ? ' q-textarea--autogrow' : '')
      }
    },

    methods: {
      focus: function focus () {
        var el = document.activeElement;
        if (
          this.$refs.input !== void 0 &&
          this.$refs.input !== el &&
          // IE can have null document.activeElement
          (el === null || el.id !== this.targetUid)
        ) {
          this.$refs.input.focus();
        }
      },

      select: function select () {
        this.$refs.input !== void 0 && this.$refs.input.select();
      },

      __onPaste: function __onPaste (e) {
        if (this.hasMask === true && this.reverseFillMask !== true) {
          var inp = e.target;
          this.__moveCursorForPaste(inp, inp.selectionStart, inp.selectionEnd);
        }
      },

      __onInput: function __onInput (e) {
        if (e && e.target && e.target.composing === true) {
          return
        }

        if (this.type === 'file') {
          this.$emit('input', e.target.files);
          return
        }

        var val = e.target.value;

        if (this.hasMask === true) {
          this.__updateMaskValue(val, false, e.inputType);
        }
        else {
          this.__emitValue(val);
        }

        // we need to trigger it immediately too,
        // to avoid "flickering"
        this.autogrow === true && this.__adjustHeight();
      },

      __emitValue: function __emitValue (val, stopWatcher) {
        var this$1 = this;

        this.emitValueFn = function () {
          if (
            this$1.type !== 'number' &&
            this$1.hasOwnProperty('tempValue') === true
          ) {
            delete this$1.tempValue;
          }

          if (this$1.value !== val) {
            stopWatcher === true && (this$1.stopValueWatcher = true);
            this$1.$emit('input', val);
          }

          this$1.emitValueFn = void 0;
        };

        if (this.type === 'number') {
          this.typedNumber = true;
          this.tempValue = val;
        }

        if (this.debounce !== void 0) {
          clearTimeout(this.emitTimer);
          this.tempValue = val;
          this.emitTimer = setTimeout(this.emitValueFn, this.debounce);
        }
        else {
          this.emitValueFn();
        }
      },

      // textarea only
      __adjustHeight: function __adjustHeight () {
        var inp = this.$refs.input;
        if (inp !== void 0) {
          var parentStyle = inp.parentNode.style;

          // reset height of textarea to a small size to detect the real height
          // but keep the total control size the same
          parentStyle.marginBottom = (inp.scrollHeight - 1) + 'px';
          inp.style.height = '1px';

          inp.style.height = inp.scrollHeight + 'px';
          parentStyle.marginBottom = '';
        }
      },

      __onChange: function __onChange (e) {
        this.__onComposition(e);

        clearTimeout(this.emitTimer);
        this.emitValueFn !== void 0 && this.emitValueFn();

        this.$emit('change', e);
      },

      __onFinishEditing: function __onFinishEditing (e) {
        var this$1 = this;

        e !== void 0 && stop(e);

        clearTimeout(this.emitTimer);
        this.emitValueFn !== void 0 && this.emitValueFn();

        this.typedNumber = false;
        this.stopValueWatcher = false;
        delete this.tempValue;

        this.type !== 'file' && this.$nextTick(function () {
          if (this$1.$refs.input !== void 0) {
            this$1.$refs.input.value = this$1.innerValue !== void 0 ? this$1.innerValue : '';
          }
        });
      },

      __getControl: function __getControl (h) {
        var on = Object.assign({}, this.$listeners,
          {input: this.__onInput,
          paste: this.__onPaste,
          // Safari < 10.2 & UIWebView doesn't fire compositionend when
          // switching focus before confirming composition choice
          // this also fixes the issue where some browsers e.g. iOS Chrome
          // fires "change" instead of "input" on autocomplete.
          change: this.__onChange,
          blur: this.__onFinishEditing,
          focus: stop});

        on.compositionstart = on.compositionupdate = on.compositionend = this.__onComposition;

        if (this.hasMask === true) {
          on.keydown = this.__onMaskedKeydown;
        }

        var attrs = Object.assign({}, {tabindex: 0,
          'data-autofocus': this.autofocus,
          rows: this.type === 'textarea' ? 6 : void 0,
          'aria-label': this.label,
          name: this.nameProp},
          this.$attrs,
          {id: this.targetUid,
          type: this.type,
          maxlength: this.maxlength});

        if (this.disable === true) {
          attrs.disabled = '';
          attrs['aria-disabled'] = '';
        }
        else if (this.readonly === true) {
          attrs.readonly = '';
          attrs['aria-readonly'] = '';
        }

        if (this.autogrow === true) {
          attrs.rows = 1;
          on.animationend = this.__adjustHeight;
        }

        return h(this.isTextarea === true ? 'textarea' : 'input', {
          ref: 'input',
          staticClass: 'q-field__native q-placeholder',
          style: this.inputStyle,
          class: this.inputClass,
          attrs: attrs,
          on: on,
          domProps: this.type !== 'file'
            ? {
              value: this.hasOwnProperty('tempValue') === true
                ? this.tempValue
                : (this.innerValue !== void 0 ? this.innerValue : '')
            }
            : this.formDomProps
        })
      }
    },

    mounted: function mounted () {
      // textarea only
      this.autogrow === true && this.__adjustHeight();
    },

    beforeDestroy: function beforeDestroy () {
      this.__onFinishEditing();
    }
  });

  var QTooltip = Vue.extend({
    name: 'QTooltip',

    mixins: [ AnchorMixin, ModelToggleMixin, PortalMixin, TransitionMixin ],

    props: {
      maxHeight: {
        type: String,
        default: null
      },
      maxWidth: {
        type: String,
        default: null
      },

      transitionShow: {
        default: 'jump-down'
      },
      transitionHide: {
        default: 'jump-up'
      },

      anchor: {
        type: String,
        default: 'bottom middle',
        validator: validatePosition
      },
      self: {
        type: String,
        default: 'top middle',
        validator: validatePosition
      },
      offset: {
        type: Array,
        default: function () { return [14, 14]; },
        validator: validateOffset
      },

      scrollTarget: {
        default: void 0
      },

      delay: {
        type: Number,
        default: 0
      },

      hideDelay: {
        type: Number,
        default: 0
      }
    },

    computed: {
      anchorOrigin: function anchorOrigin () {
        return parsePosition(this.anchor)
      },

      selfOrigin: function selfOrigin () {
        return parsePosition(this.self)
      },

      hideOnRouteChange: function hideOnRouteChange () {
        return this.persistent !== true
      }
    },

    methods: {
      __show: function __show (evt) {
        var this$1 = this;

        this.__showPortal();

        this.__nextTick(function () {
          this$1.observer = new MutationObserver(function () { return this$1.updatePosition(); });
          this$1.observer.observe(this$1.__portal.$el, { attributes: false, childList: true, characterData: true, subtree: true });
          this$1.updatePosition();
          this$1.__configureScrollTarget();
        });

        this.__setTimeout(function () {
          this$1.$emit('show', evt);
        }, 300);
      },

      __hide: function __hide (evt) {
        var this$1 = this;

        this.__anchorCleanup();

        this.__setTimeout(function () {
          this$1.__hidePortal();
          this$1.$emit('hide', evt);
        }, 300);
      },

      __anchorCleanup: function __anchorCleanup () {
        if (this.observer !== void 0) {
          this.observer.disconnect();
          this.observer = void 0;
        }

        this.__unconfigureScrollTarget();
        cleanEvt(this, 'tooltipTemp');
      },

      updatePosition: function updatePosition () {
        if (this.anchorEl === void 0 || this.__portal === void 0) {
          return
        }

        var el = this.__portal.$el;

        if (el.nodeType === 8) { // IE replaces the comment with delay
          setTimeout(this.updatePosition, 25);
          return
        }

        setPosition({
          el: el,
          offset: this.offset,
          anchorEl: this.anchorEl,
          anchorOrigin: this.anchorOrigin,
          selfOrigin: this.selfOrigin,
          maxHeight: this.maxHeight,
          maxWidth: this.maxWidth
        });
      },

      __delayShow: function __delayShow (evt) {
        var this$1 = this;

        if (this.$q.platform.is.mobile === true) {
          clearSelection();
          document.body.classList.add('non-selectable');

          var target = getTouchTarget(this.anchorEl);
          var evts = ['touchmove', 'touchcancel', 'touchend', 'click']
            .map(function (e) { return ([ target, e, '__delayHide', 'passiveCapture' ]); });

          addEvt(this, 'tooltipTemp', evts);
        }

        this.__setTimeout(function () {
          this$1.show(evt);
        }, this.delay);
      },

      __delayHide: function __delayHide (evt) {
        var this$1 = this;

        this.__clearTimeout();

        if (this.$q.platform.is.mobile === true) {
          cleanEvt(this, 'tooltipTemp');
          clearSelection();
          // delay needed otherwise selection still occurs
          setTimeout(function () {
            document.body.classList.remove('non-selectable');
          }, 10);
        }

        this.__setTimeout(function () {
          this$1.hide(evt);
        }, this.hideDelay);
      },

      __configureAnchorEl: function __configureAnchorEl () {
        if (this.noParentEvent === true || this.anchorEl === void 0) { return }

        var evts = this.$q.platform.is.mobile === true
          ? [
            [ this.anchorEl, 'touchstart', '__delayShow', 'passive' ]
          ]
          : [
            [ this.anchorEl, 'mouseenter', '__delayShow', 'passive' ],
            [ this.anchorEl, 'mouseleave', '__delayHide', 'passive' ]
          ];

        addEvt(this, 'anchor', evts);
      },

      __unconfigureScrollTarget: function __unconfigureScrollTarget () {
        if (this.__scrollTarget !== void 0) {
          this.__changeScrollEvent(this.__scrollTarget);
          this.__scrollTarget = void 0;
        }
      },

      __configureScrollTarget: function __configureScrollTarget () {
        if (this.anchorEl !== void 0 || this.scrollTarget !== void 0) {
          this.__scrollTarget = getScrollTarget(this.anchorEl, this.scrollTarget);
          var fn = this.noParentEvent === true
            ? this.updatePosition
            : this.hide;

          this.__changeScrollEvent(this.__scrollTarget, fn);
        }
      },

      __renderPortal: function __renderPortal (h) {
        return h('transition', {
          props: { name: this.transition }
        }, [
          this.showing === true ? h('div', {
            staticClass: 'q-tooltip q-tooltip--style q-position-engine no-pointer-events',
            class: this.contentClass,
            style: this.contentStyle,
            attrs: {
              role: 'complementary'
            }
          }, slot(this, 'default')) : null
        ])
      }
    },

    mounted: function mounted () {
      this.__processModelChange(this.value);
    }
  });

  var QList = Vue.extend({
    name: 'QList',

    mixins: [ DarkMixin ],

    props: {
      bordered: Boolean,
      dense: Boolean,
      separator: Boolean,
      padding: Boolean
    },

    computed: {
      classes: function classes () {
        return 'q-list' +
          (this.bordered === true ? ' q-list--bordered' : '') +
          (this.dense === true ? ' q-list--dense' : '') +
          (this.separator === true ? ' q-list--separator' : '') +
          (this.isDark === true ? ' q-list--dark' : '') +
          (this.padding === true ? ' q-list--padding' : '')
      }
    },

    render: function render (h) {
      return h('div', {
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QItem = Vue.extend({
    name: 'QItem',

    mixins: [ DarkMixin, RouterLinkMixin, TagMixin ],

    props: {
      active: Boolean,

      clickable: Boolean,
      dense: Boolean,
      insetLevel: Number,

      tabindex: [ String, Number ],

      focused: Boolean,
      manualFocus: Boolean
    },

    computed: {
      isClickable: function isClickable () {
        return this.disable !== true && (
          this.clickable === true ||
          this.hasRouterLink === true ||
          this.tag === 'a' ||
          this.tag === 'label'
        )
      },

      classes: function classes () {
        var obj;

        return ( obj = {
          'q-item--clickable q-link cursor-pointer': this.isClickable,
          'q-focusable q-hoverable': this.isClickable === true && this.manualFocus === false,

          'q-manual-focusable': this.isClickable === true && this.manualFocus === true,
          'q-manual-focusable--focused': this.isClickable === true && this.focused === true,

          'q-item--dense': this.dense,
          'q-item--dark': this.isDark,
          'q-item--active': this.active
        }, obj[this.activeClass] = this.active === true && this.hasRouterLink !== true && this.activeClass !== void 0, obj['disabled'] = this.disable, obj )
      },

      style: function style () {
        var obj;

        if (this.insetLevel !== void 0) {
          var dir = this.$q.lang.rtl === true ? 'Right' : 'Left';
          return ( obj = {}, obj['padding' + dir] = (16 + this.insetLevel * 56) + 'px', obj )
        }
      }
    },

    methods: {
      __getContent: function __getContent (h) {
        var child = uniqueSlot(this, 'default', []);
        this.isClickable === true && child.unshift(
          h('div', { staticClass: 'q-focus-helper', attrs: { tabindex: -1 }, ref: 'blurTarget' })
        );
        return child
      },

      __onClick: function __onClick (e) {
        if (this.isClickable === true) {
          if (this.$refs.blurTarget !== void 0) {
            if (e.qKeyEvent !== true && document.activeElement === this.$el) {
              this.$refs.blurTarget.focus();
            }
            else if (document.activeElement === this.$refs.blurTarget) {
              this.$el.focus();
            }
          }

          this.$emit('click', e);
        }
      },

      __onKeyup: function __onKeyup (e) {
        if (this.isClickable === true && isKeyCode(e, 13) === true) {
          stopAndPrevent(e);

          // for ripple
          e.qKeyEvent = true;

          // for click trigger
          var evt = new MouseEvent('click', e);
          evt.qKeyEvent = true;
          this.$el.dispatchEvent(evt);
        }

        this.$emit('keyup', e);
      }
    },

    render: function render (h) {
      var data = {
        staticClass: 'q-item q-item-type row no-wrap',
        class: this.classes,
        style: this.style
      };

      var evtProp = this.hasRouterLink === true ? 'nativeOn' : 'on';
      data[evtProp] = Object.assign({}, this.$listeners,
        {click: this.__onClick,
        keyup: this.__onKeyup});

      if (this.isClickable === true) {
        data.attrs = {
          tabindex: this.tabindex || '0'
        };
      }

      if (this.hasRouterLink === true) {
        data.tag = 'a';
        data.props = this.routerLinkProps;

        return h('router-link', data, this.__getContent(h))
      }

      return h(
        this.tag,
        data,
        this.__getContent(h)
      )
    }
  });

  var QItemSection = Vue.extend({
    name: 'QItemSection',

    props: {
      avatar: Boolean,
      thumbnail: Boolean,
      side: Boolean,
      top: Boolean,
      noWrap: Boolean
    },

    computed: {
      classes: function classes () {
        var obj;

        var side = this.avatar || this.side || this.thumbnail;

        return ( obj = {
          'q-item__section--top': this.top,
          'q-item__section--avatar': this.avatar,
          'q-item__section--thumbnail': this.thumbnail,
          'q-item__section--side': side,
          'q-item__section--nowrap': this.noWrap,
          'q-item__section--main': !side
        }, obj[("justify-" + (this.top ? 'start' : 'center'))] = true, obj )
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-item__section column',
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  function run (e, btn, vm) {
    if (btn.handler) {
      btn.handler(e, vm, vm.caret);
    }
    else {
      vm.runCmd(btn.cmd, btn.param);
    }
  }

  function __getGroup (h, children) {
    return h('div', {
      staticClass: 'q-editor__toolbar-group'
    }, children)
  }

  function getBtn (h, vm, btn, clickHandler, active) {
    if ( active === void 0 ) active = false;

    var
      toggled = active || (btn.type === 'toggle'
        ? (btn.toggled ? btn.toggled(vm) : btn.cmd && vm.caret.is(btn.cmd, btn.param))
        : false),
      child = [],
      events = {
        click: function click (e) {
          clickHandler && clickHandler();
          run(e, btn, vm);
        }
      };

    if (btn.tip && vm.$q.platform.is.desktop) {
      var Key = btn.key
        ? h('div', [h('small', ("(CTRL + " + (String.fromCharCode(btn.key)) + ")"))])
        : null;
      child.push(
        h(QTooltip, { props: { delay: 1000 } }, [
          h('div', { domProps: { innerHTML: btn.tip } }),
          Key
        ])
      );
    }

    return h(QBtn, {
      props: Object.assign({}, vm.buttonProps,
        {icon: btn.icon,
        color: toggled ? btn.toggleColor || vm.toolbarToggleColor : btn.color || vm.toolbarColor,
        textColor: toggled && !vm.toolbarPush ? null : btn.textColor || vm.toolbarTextColor,
        label: btn.label,
        disable: btn.disable ? (typeof btn.disable === 'function' ? btn.disable(vm) : true) : false,
        size: 'sm'}),
      on: events
    }, child)
  }

  function getDropdown (h, vm, btn) {
    var
      label = btn.label,
      icon = btn.icon,
      onlyIcons = btn.list === 'only-icons',
      contentClass,
      Items;

    function closeDropdown () {
      Dropdown.componentInstance.hide();
    }

    if (onlyIcons) {
      Items = btn.options.map(function (btn) {
        var active = btn.type === void 0
          ? vm.caret.is(btn.cmd, btn.param)
          : false;

        if (active) {
          label = btn.tip;
          icon = btn.icon;
        }
        return getBtn(h, vm, btn, closeDropdown, active)
      });
      contentClass = vm.toolbarBackgroundClass;
      Items = [
        __getGroup(h, Items)
      ];
    }
    else {
      var activeClass = vm.toolbarToggleColor !== void 0
        ? ("text-" + (vm.toolbarToggleColor))
        : null;
      var inactiveClass = vm.toolbarTextColor !== void 0
        ? ("text-" + (vm.toolbarTextColor))
        : null;

      Items = btn.options.map(function (btn) {
        var disable = btn.disable ? btn.disable(vm) : false;
        var active = btn.type === void 0
          ? vm.caret.is(btn.cmd, btn.param)
          : false;

        if (active) {
          label = btn.tip;
          icon = btn.icon;
        }

        var htmlTip = btn.htmlTip;

        return h(
          QItem,
          {
            props: { active: active, activeClass: activeClass, clickable: true, disable: disable, dense: true },
            on: {
              click: function click (e) {
                closeDropdown();
                vm.$refs.content && vm.$refs.content.focus();
                vm.caret.restore();
                run(e, btn, vm);
              }
            }
          },
          [
            btn.list === 'no-icons'
              ? null
              : h(QItemSection, {
                class: active ? activeClass : inactiveClass,
                props: { side: true }
              }, [
                h(QIcon, { props: { name: btn.icon } })
              ]),

            h(QItemSection, [
              htmlTip
                ? h('div', {
                  domProps: { innerHTML: btn.htmlTip }
                })
                : (btn.tip ? h('div', [ btn.tip ]) : null)
            ])
          ]
        )
      });
      contentClass = [vm.toolbarBackgroundClass, inactiveClass];
      Items = [
        h(QList, [ Items ])
      ];
    }

    var highlight = btn.highlight && label !== btn.label;
    var Dropdown = h(
      QBtnDropdown,
      {
        props: Object.assign({}, vm.buttonProps,
          {noCaps: true,
          noWrap: true,
          color: highlight ? vm.toolbarToggleColor : vm.toolbarColor,
          textColor: highlight && !vm.toolbarPush ? null : vm.toolbarTextColor,
          label: btn.fixedLabel ? btn.label : label,
          icon: btn.fixedIcon ? btn.icon : icon,
          contentClass: contentClass})
      },
      Items
    );
    return Dropdown
  }

  function getToolbar (h, vm) {
    if (vm.caret) {
      return vm.buttons
        .filter(function (f) {
          return !vm.isViewingSource || f.find(function (fb) { return fb.cmd === 'viewsource'; })
        })
        .map(function (group) { return __getGroup(
          h,
          group.map(function (btn) {
            if (vm.isViewingSource && btn.cmd !== 'viewsource') {
              return false
            }

            if (btn.type === 'slot') {
              return slot(vm, btn.slot)
            }

            if (btn.type === 'dropdown') {
              return getDropdown(h, vm, btn)
            }

            return getBtn(h, vm, btn)
          })
        ); })
    }
  }

  function getFonts (defaultFont, defaultFontLabel, defaultFontIcon, fonts) {
    if ( fonts === void 0 ) fonts = {};

    var aliases = Object.keys(fonts);
    if (aliases.length === 0) {
      return {}
    }

    var def = {
      default_font: {
        cmd: 'fontName',
        param: defaultFont,
        icon: defaultFontIcon,
        tip: defaultFontLabel
      }
    };

    aliases.forEach(function (alias) {
      var name = fonts[alias];
      def[alias] = {
        cmd: 'fontName',
        param: name,
        icon: defaultFontIcon,
        tip: name,
        htmlTip: ("<font face=\"" + name + "\">" + name + "</font>")
      };
    });

    return def
  }

  function getLinkEditor (h, vm, ie11) {
    if (vm.caret) {
      var color = vm.toolbarColor || vm.toolbarTextColor;
      var link = vm.editLinkUrl;
      var updateLink = function () {
        vm.caret.restore();

        if (link !== vm.editLinkUrl) {
          document.execCommand('createLink', false, link === '' ? ' ' : link);
        }

        vm.editLinkUrl = null;

        ie11 === true && vm.$nextTick(vm.__onInput);
      };

      return [
        h('div', { staticClass: 'q-mx-xs', 'class': ("text-" + color) }, [((vm.$q.lang.editor.url) + ": ")]),
        h(QInput, {
          key: 'qedt_btm_input',
          staticClass: 'q-ma-none q-pa-none col q-editor-input',
          props: {
            value: link,
            color: color,
            autofocus: true,
            borderless: true,
            dense: true
          },
          on: {
            input: function (val) { link = val; },
            keydown: function (event) {
              if (shouldIgnoreKey(event) === true) {
                return
              }

              switch (event.keyCode) {
                case 13: // ENTER key
                  prevent(event);
                  return updateLink()
                case 27: // ESCAPE key
                  prevent(event);
                  vm.caret.restore();
                  if (!vm.editLinkUrl || vm.editLinkUrl === 'https://') {
                    document.execCommand('unlink');
                  }
                  vm.editLinkUrl = null;
                  break
              }
            }
          }
        }),
        __getGroup(h, [
          h(QBtn, {
            key: 'qedt_btm_rem',
            attrs: { tabindex: -1 },
            props: Object.assign({}, vm.buttonProps,
              {label: vm.$q.lang.label.remove,
              noCaps: true}),
            on: {
              click: function () {
                vm.caret.restore();
                document.execCommand('unlink');
                vm.editLinkUrl = null;

                ie11 === true && vm.$nextTick(vm.__onInput);
              }
            }
          }),
          h(QBtn, {
            key: 'qedt_btm_upd',
            props: Object.assign({}, vm.buttonProps,
              {label: vm.$q.lang.label.update,
              noCaps: true}),
            on: {
              click: updateLink
            }
          })
        ])
      ]
    }
  }

  function getBlockElement (el, parent) {
    if (parent && el === parent) {
      return null
    }

    var nodeName = el.nodeName.toLowerCase();

    if (['div', 'li', 'ul', 'ol', 'blockquote'].includes(nodeName) === true) {
      return el
    }

    var
      style = window.getComputedStyle
        ? window.getComputedStyle(el)
        : el.currentStyle,
      display = style.display;

    if (display === 'block' || display === 'table') {
      return el
    }

    return getBlockElement(el.parentNode)
  }

  function isChildOf (el, parent) {
    return el === parent
      ? false
      : (parent === document ? document.body : parent).contains(el)
  }

  var urlRegex = /^https?:\/\//;

  var Caret = function Caret (el, vm) {
    this.el = el;
    this.vm = vm;
    this._range = null;
  };

  var prototypeAccessors = { selection: { configurable: true },hasSelection: { configurable: true },range: { configurable: true },parent: { configurable: true },blockParent: { configurable: true } };

  prototypeAccessors.selection.get = function () {
    if (this.el) {
      var sel = document.getSelection();

      // only when the selection in element
      if (isChildOf(sel.anchorNode, this.el) && isChildOf(sel.focusNode, this.el)) {
        return sel
      }
    }

    return null
  };

  prototypeAccessors.hasSelection.get = function () {
    return this.selection !== null
      ? this.selection.toString().length > 0
      : false
  };

  prototypeAccessors.range.get = function () {
    var sel = this.selection;

    if (sel !== null && sel.rangeCount) {
      return sel.getRangeAt(0)
    }

    return this._range
  };

  prototypeAccessors.parent.get = function () {
    var range = this.range;

    if (range !== null) {
      var node = range.startContainer;

      return node.nodeType === document.ELEMENT_NODE
        ? node
        : node.parentNode
    }

    return null
  };

  prototypeAccessors.blockParent.get = function () {
    var parent = this.parent;

    if (parent !== null) {
      return getBlockElement(parent, this.el)
    }

    return null
  };

  Caret.prototype.save = function save (range) {
      if ( range === void 0 ) range = this.range;

    if (range !== null) {
      this._range = range;
    }
  };

  Caret.prototype.restore = function restore (range) {
      if ( range === void 0 ) range = this._range;

    var
      r = document.createRange(),
      sel = document.getSelection();

    if (range !== null) {
      r.setStart(range.startContainer, range.startOffset);
      r.setEnd(range.endContainer, range.endOffset);
      sel.removeAllRanges();
      sel.addRange(r);
    }
    else {
      sel.selectAllChildren(this.el);
      sel.collapseToEnd();
    }
  };

  Caret.prototype.hasParent = function hasParent (name, spanLevel) {
    var el = spanLevel
      ? this.parent
      : this.blockParent;

    return el !== null
      ? el.nodeName.toLowerCase() === name.toLowerCase()
      : false
  };

  Caret.prototype.hasParents = function hasParents (list, recursive, el) {
      if ( el === void 0 ) el = this.parent;

    if (el === null) {
      return false
    }

    if (el !== null && list.includes(el.nodeName.toLowerCase()) === true) {
      return true
    }

    return recursive === true
      ? this.hasParents(list, recursive, el.parentNode)
      : false
  };

  Caret.prototype.is = function is (cmd, param) {
    switch (cmd) {
      case 'formatBlock':
        if (param === 'DIV' && this.parent === this.el) {
          return true
        }
        return this.hasParent(param, param === 'PRE')
      case 'link':
        return this.hasParent('A', true)
      case 'fontSize':
        return document.queryCommandValue(cmd) === param
      case 'fontName':
        var res = document.queryCommandValue(cmd);
        return res === ("\"" + param + "\"") || res === param
      case 'fullscreen':
        return this.vm.inFullscreen
      case 'viewsource':
        return this.vm.isViewingSource
      case void 0:
        return false
      default:
        var state = document.queryCommandState(cmd);
        return param !== void 0 ? state === param : state
    }
  };

  Caret.prototype.getParentAttribute = function getParentAttribute (attrib) {
    if (this.parent !== null) {
      return this.parent.getAttribute(attrib)
    }

    return null
  };

  Caret.prototype.can = function can (name) {
    if (name === 'outdent') {
      return this.hasParents(['blockquote', 'li'], true)
    }

    if (name === 'indent') {
      return this.hasParents(['li'], true)
    }

    if (name === 'link') {
      return this.selection !== null || this.is('link')
    }
  };

  Caret.prototype.apply = function apply (cmd, param, done) {
      if ( done === void 0 ) done = noop;

    if (cmd === 'formatBlock') {
      if (['BLOCKQUOTE', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(param) && this.is(cmd, param)) {
        cmd = 'outdent';
        param = null;
      }

      if (param === 'PRE' && this.is(cmd, 'PRE')) {
        param = 'P';
      }
    }
    else if (cmd === 'print') {
      done();

      var win = window.open();

      win.document.write(("\n        <!doctype html>\n        <html>\n          <head>\n            <title>Print - " + (document.title) + "</title>\n          </head>\n          <body>\n            <div>" + (this.el.innerHTML) + "</div>\n          </body>\n        </html>\n      "));
      win.print();
      win.close();

      return
    }
    else if (cmd === 'link') {
      var link = this.getParentAttribute('href');

      if (link === null) {
        var selection = this.selectWord(this.selection);
        var url = selection ? selection.toString() : '';

        if (!url.length) {
          return
        }

        this.vm.editLinkUrl = urlRegex.test(url) ? url : 'https://';
        document.execCommand('createLink', false, this.vm.editLinkUrl);

        this.save(selection.getRangeAt(0));
      }
      else {
        this.vm.editLinkUrl = link;

        this.range.selectNodeContents(this.parent);
        this.save();
      }

      return
    }
    else if (cmd === 'fullscreen') {
      this.vm.toggleFullscreen();
      done();

      return
    }
    else if (cmd === 'viewsource') {
      this.vm.isViewingSource = this.vm.isViewingSource === false;
      this.vm.__setContent(this.vm.value);
      done();

      return
    }

    document.execCommand(cmd, false, param);

    done();
  };

  Caret.prototype.selectWord = function selectWord (sel) {
    if (sel === null || sel.isCollapsed !== true || /* IE 11 */ sel.modify === void 0) {
      return sel
    }

    // Detect if selection is backwards
    var range = document.createRange();
    range.setStart(sel.anchorNode, sel.anchorOffset);
    range.setEnd(sel.focusNode, sel.focusOffset);
    var direction = range.collapsed ? ['backward', 'forward'] : ['forward', 'backward'];
    range.detach();

    // modify() works on the focus of the selection
    var
      endNode = sel.focusNode,
      endOffset = sel.focusOffset;
    sel.collapse(sel.anchorNode, sel.anchorOffset);
    sel.modify('move', direction[0], 'character');
    sel.modify('move', direction[1], 'word');
    sel.extend(endNode, endOffset);
    sel.modify('extend', direction[1], 'character');
    sel.modify('extend', direction[0], 'word');

    return sel
  };

  Object.defineProperties( Caret.prototype, prototypeAccessors );

  var
    toString = Object.prototype.toString,
    hasOwn = Object.prototype.hasOwnProperty,
    class2type = {};

  'Boolean Number String Function Array Date RegExp Object'.split(' ').forEach(function (name) {
    class2type['[object ' + name + ']'] = name.toLowerCase();
  });

  function type (obj) {
    return obj === null ? String(obj) : class2type[toString.call(obj)] || 'object'
  }

  function isPlainObject (obj) {
    if (!obj || type(obj) !== 'object') {
      return false
    }

    if (obj.constructor &&
      !hasOwn.call(obj, 'constructor') &&
      !hasOwn.call(obj.constructor.prototype, 'isPrototypeOf')) {
      return false
    }

    var key;
    for (key in obj) {}

    return key === undefined || hasOwn.call(obj, key)
  }

  function extend () {
    var arguments$1 = arguments;

    var
      options, name, src, copy, copyIsArray, clone,
      target = arguments[0] || {},
      i = 1,
      length = arguments.length,
      deep = false;

    if (typeof target === 'boolean') {
      deep = target;
      target = arguments[1] || {};
      i = 2;
    }

    if (Object(target) !== target && type(target) !== 'function') {
      target = {};
    }

    if (length === i) {
      target = this;
      i--;
    }

    for (; i < length; i++) {
      if ((options = arguments$1[i]) !== null) {
        for (name in options) {
          src = target[name];
          copy = options[name];

          if (target === copy) {
            continue
          }

          if (deep && copy && (isPlainObject(copy) || (copyIsArray = type(copy) === 'array'))) {
            if (copyIsArray) {
              copyIsArray = false;
              clone = src && type(src) === 'array' ? src : [];
            }
            else {
              clone = src && isPlainObject(src) ? src : {};
            }

            target[name] = extend(deep, clone, copy);
          }
          else if (copy !== undefined) {
            target[name] = copy;
          }
        }
      }
    }

    return target
  }

  var QEditor = Vue.extend({
    name: 'QEditor',

    mixins: [ FullscreenMixin, DarkMixin ],

    props: {
      value: {
        type: String,
        required: true
      },
      readonly: Boolean,
      disable: Boolean,
      minHeight: {
        type: String,
        default: '10rem'
      },
      maxHeight: String,
      height: String,
      definitions: Object,
      fonts: Object,

      toolbar: {
        type: Array,
        validator: function (v) { return v.length === 0 || v.every(function (group) { return group.length; }); },
        default: function default$1 () {
          return [
            ['left', 'center', 'right', 'justify'],
            ['bold', 'italic', 'underline', 'strike'],
            ['undo', 'redo']
          ]
        }
      },
      toolbarColor: String,
      toolbarBg: String,
      toolbarTextColor: String,
      toolbarToggleColor: {
        type: String,
        default: 'primary'
      },
      toolbarOutline: Boolean,
      toolbarPush: Boolean,
      toolbarRounded: Boolean,

      contentStyle: Object,
      contentClass: [Object, Array, String],

      square: Boolean,
      flat: Boolean,
      dense: Boolean
    },

    computed: {
      editable: function editable () {
        return !this.readonly && !this.disable
      },

      hasToolbar: function hasToolbar () {
        return this.toolbar && this.toolbar.length > 0
      },

      toolbarBackgroundClass: function toolbarBackgroundClass () {
        if (this.toolbarBg) {
          return ("bg-" + (this.toolbarBg))
        }
      },

      buttonProps: function buttonProps () {
        var flat = this.toolbarOutline !== true &&
          this.toolbarPush !== true;

        return {
          type: 'a',
          flat: flat,
          noWrap: true,
          outline: this.toolbarOutline,
          push: this.toolbarPush,
          rounded: this.toolbarRounded,
          dense: true,
          color: this.toolbarColor,
          disable: !this.editable,
          size: 'sm'
        }
      },

      buttonDef: function buttonDef () {
        var
          e = this.$q.lang.editor,
          i = this.$q.iconSet.editor;

        return {
          bold: { cmd: 'bold', icon: i.bold, tip: e.bold, key: 66 },
          italic: { cmd: 'italic', icon: i.italic, tip: e.italic, key: 73 },
          strike: { cmd: 'strikeThrough', icon: i.strikethrough, tip: e.strikethrough, key: 83 },
          underline: { cmd: 'underline', icon: i.underline, tip: e.underline, key: 85 },
          unordered: { cmd: 'insertUnorderedList', icon: i.unorderedList, tip: e.unorderedList },
          ordered: { cmd: 'insertOrderedList', icon: i.orderedList, tip: e.orderedList },
          subscript: { cmd: 'subscript', icon: i.subscript, tip: e.subscript, htmlTip: 'x<subscript>2</subscript>' },
          superscript: { cmd: 'superscript', icon: i.superscript, tip: e.superscript, htmlTip: 'x<superscript>2</superscript>' },
          link: { cmd: 'link', disable: function (vm) { return vm.caret && !vm.caret.can('link'); }, icon: i.hyperlink, tip: e.hyperlink, key: 76 },
          fullscreen: { cmd: 'fullscreen', icon: i.toggleFullscreen, tip: e.toggleFullscreen, key: 70 },
          viewsource: { cmd: 'viewsource', icon: i.viewSource, tip: e.viewSource },

          quote: { cmd: 'formatBlock', param: 'BLOCKQUOTE', icon: i.quote, tip: e.quote, key: 81 },
          left: { cmd: 'justifyLeft', icon: i.left, tip: e.left },
          center: { cmd: 'justifyCenter', icon: i.center, tip: e.center },
          right: { cmd: 'justifyRight', icon: i.right, tip: e.right },
          justify: { cmd: 'justifyFull', icon: i.justify, tip: e.justify },

          print: { type: 'no-state', cmd: 'print', icon: i.print, tip: e.print, key: 80 },
          outdent: { type: 'no-state', disable: function (vm) { return vm.caret && !vm.caret.can('outdent'); }, cmd: 'outdent', icon: i.outdent, tip: e.outdent },
          indent: { type: 'no-state', disable: function (vm) { return vm.caret && !vm.caret.can('indent'); }, cmd: 'indent', icon: i.indent, tip: e.indent },
          removeFormat: { type: 'no-state', cmd: 'removeFormat', icon: i.removeFormat, tip: e.removeFormat },
          hr: { type: 'no-state', cmd: 'insertHorizontalRule', icon: i.hr, tip: e.hr },
          undo: { type: 'no-state', cmd: 'undo', icon: i.undo, tip: e.undo, key: 90 },
          redo: { type: 'no-state', cmd: 'redo', icon: i.redo, tip: e.redo, key: 89 },

          h1: { cmd: 'formatBlock', param: 'H1', icon: i.heading1 || i.heading, tip: e.heading1, htmlTip: ("<h1 class=\"q-ma-none\">" + (e.heading1) + "</h1>") },
          h2: { cmd: 'formatBlock', param: 'H2', icon: i.heading2 || i.heading, tip: e.heading2, htmlTip: ("<h2 class=\"q-ma-none\">" + (e.heading2) + "</h2>") },
          h3: { cmd: 'formatBlock', param: 'H3', icon: i.heading3 || i.heading, tip: e.heading3, htmlTip: ("<h3 class=\"q-ma-none\">" + (e.heading3) + "</h3>") },
          h4: { cmd: 'formatBlock', param: 'H4', icon: i.heading4 || i.heading, tip: e.heading4, htmlTip: ("<h4 class=\"q-ma-none\">" + (e.heading4) + "</h4>") },
          h5: { cmd: 'formatBlock', param: 'H5', icon: i.heading5 || i.heading, tip: e.heading5, htmlTip: ("<h5 class=\"q-ma-none\">" + (e.heading5) + "</h5>") },
          h6: { cmd: 'formatBlock', param: 'H6', icon: i.heading6 || i.heading, tip: e.heading6, htmlTip: ("<h6 class=\"q-ma-none\">" + (e.heading6) + "</h6>") },
          p: { cmd: 'formatBlock', param: 'DIV', icon: i.heading, tip: e.paragraph },
          code: { cmd: 'formatBlock', param: 'PRE', icon: i.code, htmlTip: ("<code>" + (e.code) + "</code>") },

          'size-1': { cmd: 'fontSize', param: '1', icon: i.size1 || i.size, tip: e.size1, htmlTip: ("<font size=\"1\">" + (e.size1) + "</font>") },
          'size-2': { cmd: 'fontSize', param: '2', icon: i.size2 || i.size, tip: e.size2, htmlTip: ("<font size=\"2\">" + (e.size2) + "</font>") },
          'size-3': { cmd: 'fontSize', param: '3', icon: i.size3 || i.size, tip: e.size3, htmlTip: ("<font size=\"3\">" + (e.size3) + "</font>") },
          'size-4': { cmd: 'fontSize', param: '4', icon: i.size4 || i.size, tip: e.size4, htmlTip: ("<font size=\"4\">" + (e.size4) + "</font>") },
          'size-5': { cmd: 'fontSize', param: '5', icon: i.size5 || i.size, tip: e.size5, htmlTip: ("<font size=\"5\">" + (e.size5) + "</font>") },
          'size-6': { cmd: 'fontSize', param: '6', icon: i.size6 || i.size, tip: e.size6, htmlTip: ("<font size=\"6\">" + (e.size6) + "</font>") },
          'size-7': { cmd: 'fontSize', param: '7', icon: i.size7 || i.size, tip: e.size7, htmlTip: ("<font size=\"7\">" + (e.size7) + "</font>") }
        }
      },

      buttons: function buttons () {
        var this$1 = this;

        var userDef = this.definitions || {};
        var def = this.definitions || this.fonts
          ? extend(
            true,
            {},
            this.buttonDef,
            userDef,
            getFonts(
              this.defaultFont,
              this.$q.lang.editor.defaultFont,
              this.$q.iconSet.editor.font,
              this.fonts
            )
          )
          : this.buttonDef;

        return this.toolbar.map(
          function (group) { return group.map(function (token) {
            if (token.options) {
              return {
                type: 'dropdown',
                icon: token.icon,
                label: token.label,
                size: 'sm',
                dense: true,
                fixedLabel: token.fixedLabel,
                fixedIcon: token.fixedIcon,
                highlight: token.highlight,
                list: token.list,
                options: token.options.map(function (item) { return def[item]; })
              }
            }

            var obj = def[token];

            if (obj) {
              return obj.type === 'no-state' || (userDef[token] && (
                obj.cmd === void 0 || (this$1.buttonDef[obj.cmd] && this$1.buttonDef[obj.cmd].type === 'no-state')
              ))
                ? obj
                : Object.assign({ type: 'toggle' }, obj)
            }
            else {
              return {
                type: 'slot',
                slot: token
              }
            }
          }); }
        )
      },

      keys: function keys () {
        var
          k = {},
          add = function (btn) {
            if (btn.key) {
              k[btn.key] = {
                cmd: btn.cmd,
                param: btn.param
              };
            }
          };

        this.buttons.forEach(function (group) {
          group.forEach(function (token) {
            if (token.options) {
              token.options.forEach(add);
            }
            else {
              add(token);
            }
          });
        });
        return k
      },

      innerStyle: function innerStyle () {
        return this.inFullscreen
          ? this.contentStyle
          : [
            {
              minHeight: this.minHeight,
              height: this.height,
              maxHeight: this.maxHeight
            },
            this.contentStyle
          ]
      },

      innerClass: function innerClass () {
        return [
          this.contentClass,
          { col: this.inFullscreen, 'overflow-auto': this.inFullscreen || this.maxHeight }
        ]
      },

      attrs: function attrs () {
        if (this.disable === true) {
          return { 'aria-disabled': '' }
        }
        if (this.readonly === true) {
          return { 'aria-readonly': '' }
        }
      }
    },

    data: function data () {
      return {
        editWatcher: true,
        editLinkUrl: null,
        isViewingSource: false
      }
    },

    watch: {
      value: function value (v) {
        if (this.editWatcher === true) {
          this.__setContent(v);
        }
        else {
          this.editWatcher = true;
        }
      }
    },

    methods: {
      __onInput: function __onInput () {
        if (this.editWatcher === true) {
          var val = this.isViewingSource
            ? this.$refs.content.innerText
            : this.$refs.content.innerHTML;

          if (val !== this.value) {
            this.editWatcher = false;
            this.$emit('input', val);
          }
        }
      },

      __onKeydown: function __onKeydown (e) {
        this.$emit('keydown', e);

        if (e.ctrlKey !== true || shouldIgnoreKey(e) === true) {
          this.refreshToolbar();
          this.$q.platform.is.ie && this.$nextTick(this.__onInput);
          return
        }

        var key = e.keyCode;
        var target = this.keys[key];
        if (target !== void 0) {
          var cmd = target.cmd;
          var param = target.param;
          stopAndPrevent(e);
          this.runCmd(cmd, param, false);
        }
      },

      __onClick: function __onClick (e) {
        this.refreshToolbar();
        this.$emit('click', e);
      },

      __onBlur: function __onBlur () {
        var ref = this.$refs.content;
        var scrollTop = ref.scrollTop;
        var scrollHeight = ref.scrollHeight;
        this.__offsetBottom = scrollHeight - scrollTop;
        this.$q.platform.is.ie !== true && this.caret.save();
        this.$emit('blur');
      },

      __onFocus: function __onFocus () {
        var this$1 = this;

        this.$nextTick(function () {
          if (this$1.$refs.content !== void 0 && this$1.__offsetBottom !== void 0) {
            this$1.$refs.content.scrollTop = this$1.$refs.content.scrollHeight - this$1.__offsetBottom;
          }
        });
      },

      __onMouseup: function __onMouseup (e) {
        this.caret.save();
        if (this.$listeners.mouseup !== void 0) {
          this.$emit('mouseup', e);
        }
      },

      __onKeyup: function __onKeyup (e) {
        this.caret.save();
        if (this.$listeners.keyup !== void 0) {
          this.$emit('keyup', e);
        }
      },

      __onTouchend: function __onTouchend (e) {
        this.caret.save();
        if (this.$listeners.touchend !== void 0) {
          this.$emit('touchend', e);
        }
      },

      runCmd: function runCmd (cmd, param, update) {
        var this$1 = this;
        if ( update === void 0 ) update = true;

        this.focus();
        this.caret.restore();
        this.caret.apply(cmd, param, function () {
          this$1.focus();
          this$1.caret.save();
          if (this$1.$q.platform.is.ie === true || this$1.$q.platform.is.edge === true) {
            this$1.$nextTick(this$1.__onInput);
          }
          if (update) {
            this$1.refreshToolbar();
          }
        });
      },

      refreshToolbar: function refreshToolbar () {
        var this$1 = this;

        setTimeout(function () {
          this$1.editLinkUrl = null;
          this$1.$forceUpdate();
        }, 1);
      },

      focus: function focus () {
        this.$refs.content.focus();
      },

      getContentEl: function getContentEl () {
        return this.$refs.content
      },

      __setContent: function __setContent (v) {
        if (this.isViewingSource) {
          this.$refs.content.innerText = v;
        }
        else {
          this.$refs.content.innerHTML = v;
        }
      }
    },

    created: function created () {
      if (isSSR === false) {
        document.execCommand('defaultParagraphSeparator', false, 'div');
        this.defaultFont = window.getComputedStyle(document.body).fontFamily;
      }
    },

    mounted: function mounted () {
      this.caret = new Caret(this.$refs.content, this);
      this.__setContent(this.value);
      this.refreshToolbar();
    },

    render: function render (h) {
      var toolbars;

      if (this.hasToolbar) {
        var bars = [];

        bars.push(
          h('div', {
            key: 'qedt_top',
            staticClass: 'q-editor__toolbar row no-wrap scroll-x',
            class: this.toolbarBackgroundClass
          }, getToolbar(h, this))
        );

        this.editLinkUrl !== null && bars.push(
          h('div', {
            key: 'qedt_btm',
            staticClass: 'q-editor__toolbar row no-wrap items-center scroll-x',
            class: this.toolbarBackgroundClass
          }, getLinkEditor(h, this, this.$q.platform.is.ie))
        );

        toolbars = h('div', {
          key: 'toolbar_ctainer',
          staticClass: 'q-editor__toolbars-container'
        }, bars);
      }

      var on = Object.assign({}, this.$listeners,
        {input: this.__onInput,
        keydown: this.__onKeydown,
        click: this.__onClick,
        blur: this.__onBlur,
        focus: this.__onFocus,

        // save caret
        mouseup: this.__onMouseup,
        keyup: this.__onKeyup,
        touchend: this.__onTouchend});

      return h(
        'div',
        {
          staticClass: 'q-editor',
          style: {
            height: this.inFullscreen === true ? '100vh' : null
          },
          'class': {
            disabled: this.disable,
            'fullscreen column': this.inFullscreen,
            'q-editor--square no-border-radius': this.square,
            'q-editor--flat': this.flat,
            'q-editor--dense': this.dense,
            'q-editor--dark q-dark': this.isDark
          },
          attrs: this.attrs
        },
        [
          toolbars,

          h(
            'div',
            {
              ref: 'content',
              staticClass: "q-editor__content",
              style: this.innerStyle,
              class: this.innerClass,
              attrs: { contenteditable: this.editable },
              domProps: isSSR
                ? { innerHTML: this.value }
                : undefined,
              on: on
            }
          )
        ]
      )
    }
  });

  var QItemLabel = Vue.extend({
    name: 'QItemLabel',

    props: {
      overline: Boolean,
      caption: Boolean,
      header: Boolean,
      lines: [Number, String]
    },

    computed: {
      classes: function classes () {
        return {
          'q-item__label--overline text-overline': this.overline,
          'q-item__label--caption text-caption': this.caption,
          'q-item__label--header': this.header,
          'ellipsis': parseInt(this.lines, 10) === 1
        }
      },

      style: function style () {
        if (this.lines !== void 0 && parseInt(this.lines, 10) > 1) {
          return {
            overflow: 'hidden',
            display: '-webkit-box',
            '-webkit-box-orient': 'vertical',
            '-webkit-line-clamp': this.lines
          }
        }
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-item__label',
        style: this.style,
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QSlideTransition = Vue.extend({
    name: 'QSlideTransition',

    props: {
      appear: Boolean,
      duration: {
        type: Number,
        default: 300
      }
    },

    methods: {
      __begin: function __begin (el, height, done) {
        el.style.overflowY = 'hidden';
        if (height !== void 0) {
          el.style.height = height + "px";
        }
        el.style.transition = "height " + (this.duration) + "ms cubic-bezier(.25, .8, .50, 1)";

        this.animating = true;
        this.done = done;
      },

      __end: function __end (el, event) {
        el.style.overflowY = null;
        el.style.height = null;
        el.style.transition = null;
        this.__cleanup();
        event !== this.lastEvent && this.$emit(event);
      },

      __cleanup: function __cleanup () {
        this.done && this.done();
        this.done = null;
        this.animating = false;

        clearTimeout(this.timer);
        clearTimeout(this.timerFallback);
        this.el !== void 0 && this.el.removeEventListener('transitionend', this.animListener);
        this.animListener = null;
      }
    },

    beforeDestroy: function beforeDestroy () {
      this.animating && this.__cleanup();
    },

    render: function render (h) {
      var this$1 = this;

      return h('transition', {
        props: {
          css: false,
          appear: this.appear
        },
        on: cache(this, 'tr', {
          enter: function (el, done) {
            var pos = 0;
            this$1.el = el;

            if (this$1.animating === true) {
              this$1.__cleanup();
              pos = el.offsetHeight === el.scrollHeight ? 0 : void 0;
            }
            else {
              this$1.lastEvent = 'hide';
            }

            this$1.__begin(el, pos, done);

            this$1.timer = setTimeout(function () {
              el.style.height = (el.scrollHeight) + "px";
              this$1.animListener = function (ev) {
                if (Object(ev) !== ev || ev.target === el) {
                  this$1.__end(el, 'show');
                }
              };
              el.addEventListener('transitionend', this$1.animListener);
              this$1.timerFallback = setTimeout(this$1.animListener, this$1.duration * 1.1);
            }, 100);
          },

          leave: function (el, done) {
            var pos;
            this$1.el = el;

            if (this$1.animating === true) {
              this$1.__cleanup();
            }
            else {
              this$1.lastEvent = 'show';
              pos = el.scrollHeight;
            }

            this$1.__begin(el, pos, done);

            this$1.timer = setTimeout(function () {
              el.style.height = 0;
              this$1.animListener = function (ev) {
                if (Object(ev) !== ev || ev.target === el) {
                  this$1.__end(el, 'hide');
                }
              };
              el.addEventListener('transitionend', this$1.animListener);
              this$1.timerFallback = setTimeout(this$1.animListener, this$1.duration * 1.1);
            }, 100);
          }
        })
      }, slot(this, 'default'))
    }
  });

  var QSeparator = Vue.extend({
    name: 'QSeparator',

    mixins: [ DarkMixin ],

    props: {
      spaced: Boolean,
      inset: [Boolean, String],
      vertical: Boolean,
      color: String
    },

    computed: {
      insetClass: function insetClass () {
        switch (this.inset) {
          case true:
            return ' q-separator--inset'
          case 'item':
            return ' q-separator--item-inset'
          case 'item-thumbnail':
            return ' q-separator--item-thumbnail-inset'
          default:
            return ''
        }
      },

      classes: function classes () {
        return 'q-separator' + this.insetClass +
          " q-separator--" + (this.vertical === true ? 'vertical self-stretch' : 'horizontal col-grow') +
          (this.color !== void 0 ? (" bg-" + (this.color)) : '') +
          (this.isDark === true ? ' q-separator--dark' : '') +
          (this.spaced === true ? ' q-separator--spaced' : '')
      },

      attrs: function attrs () {
        return {
          role: 'separator',
          'aria-orientation': this.vertical === true ? 'vertical' : 'horizontal'
        }
      }
    },

    render: function render (h) {
      return h('hr', {
        staticClass: 'q-separator',
        class: this.classes,
        attrs: this.attrs,
        on: this.$listeners
      })
    }
  });

  var eventName = 'q:expansion-item:close';

  var QExpansionItem = Vue.extend({
    name: 'QExpansionItem',

    mixins: [ DarkMixin, RouterLinkMixin, ModelToggleMixin ],

    props: {
      icon: String,

      label: String,
      labelLines: [ Number, String ],

      caption: String,
      captionLines: [ Number, String ],

      dense: Boolean,

      expandIcon: String,
      expandedIcon: String,
      expandIconClass: [ Array, String, Object ],
      duration: Number,

      headerInsetLevel: Number,
      contentInsetLevel: Number,

      expandSeparator: Boolean,
      defaultOpened: Boolean,
      expandIconToggle: Boolean,
      switchToggleSide: Boolean,
      denseToggle: Boolean,
      group: String,
      popup: Boolean,

      headerStyle: [Array, String, Object],
      headerClass: [Array, String, Object]
    },

    data: function data () {
      return {
        showing: this.value !== void 0
          ? this.value
          : this.defaultOpened
      }
    },

    watch: {
      showing: function showing (val) {
        val === true && this.group !== void 0 && this.$root.$emit(eventName, this);
      },

      group: function group (newVal, oldVal) {
        if (newVal !== void 0 && oldVal === void 0) {
          this.$root.$on(eventName, this.__eventHandler);
        }
        else if (newVal === void 0 && oldVal !== void 0) {
          this.$root.$off(eventName, this.__eventHandler);
        }
      }
    },

    computed: {
      classes: function classes () {
        return "q-expansion-item--" + (this.showing === true ? 'expanded' : 'collapsed') +
          " q-expansion-item--" + (this.popup === true ? 'popup' : 'standard')
      },

      contentStyle: function contentStyle () {
        var obj;

        if (this.contentInsetLevel !== void 0) {
          var dir = this.$q.lang.rtl === true ? 'Right' : 'Left';
          return ( obj = {}, obj['padding' + dir] = (this.contentInsetLevel * 56) + 'px', obj )
        }
      },

      isClickable: function isClickable () {
        return this.hasRouterLink === true || this.expandIconToggle !== true
      },

      expansionIcon: function expansionIcon () {
        return this.expandedIcon !== void 0 && this.showing === true
          ? this.expandedIcon
          : this.expandIcon || this.$q.iconSet.expansionItem[this.denseToggle === true ? 'denseIcon' : 'icon']
      },

      activeToggleIcon: function activeToggleIcon () {
        return this.disable !== true && (this.hasRouterLink === true || this.expandIconToggle === true)
      }
    },

    methods: {
      __onHeaderClick: function __onHeaderClick (e) {
        this.hasRouterLink !== true && this.toggle(e);
        this.$emit('click', e);
      },

      __toggleIconKeyboard: function __toggleIconKeyboard (e) {
        e.keyCode === 13 && this.__toggleIcon(e, true);
      },

      __toggleIcon: function __toggleIcon (e, keyboard) {
        keyboard !== true && this.$refs.blurTarget !== void 0 && this.$refs.blurTarget.focus();
        this.toggle(e);
        stopAndPrevent(e);
      },

      __eventHandler: function __eventHandler (comp) {
        this !== comp && this.group === comp.group && this.hide();
      },

      __getToggleIcon: function __getToggleIcon (h) {
        var data = {
          staticClass: ("q-focusable relative-position cursor-pointer" + (this.denseToggle === true && this.switchToggleSide === true ? ' items-end' : '')),
          class: this.expandIconClass,
          props: {
            side: this.switchToggleSide !== true,
            avatar: this.switchToggleSide
          }
        };

        var child = [
          h(QIcon, {
            staticClass: 'q-expansion-item__toggle-icon',
            class: this.expandedIcon === void 0 && this.showing === true
              ? 'q-expansion-item__toggle-icon--rotated'
              : void 0,
            props: { name: this.expansionIcon }
          })
        ];

        if (this.activeToggleIcon === true) {
          Object.assign(data, {
            attrs: { tabindex: 0 },
            on: cache(this, 'inpExt', {
              click: this.__toggleIcon,
              keyup: this.__toggleIconKeyboard
            })
          });

          child.unshift(
            h('div', {
              ref: 'blurTarget',
              staticClass: 'q-expansion-item__toggle-focus q-icon q-focus-helper q-focus-helper--rounded',
              attrs: { tabindex: -1 }
            })
          );
        }

        return h(QItemSection, data, child)
      },

      __getHeader: function __getHeader (h) {
        var child;

        if (this.$scopedSlots.header !== void 0) {
          child = this.$scopedSlots.header().slice();
        }
        else {
          child = [
            h(QItemSection, [
              h(QItemLabel, {
                props: { lines: this.labelLines }
              }, [ this.label || '' ]),

              this.caption
                ? h(QItemLabel, {
                  props: { lines: this.captionLines, caption: true }
                }, [ this.caption ])
                : null
            ])
          ];

          this.icon && child[this.switchToggleSide === true ? 'push' : 'unshift'](
            h(QItemSection, {
              props: {
                side: this.switchToggleSide === true,
                avatar: this.switchToggleSide !== true
              }
            }, [
              h(QIcon, {
                props: { name: this.icon }
              })
            ])
          );
        }

        this.disable !== true && child[this.switchToggleSide === true ? 'unshift' : 'push'](
          this.__getToggleIcon(h)
        );

        var data = {
          ref: 'item',
          style: this.headerStyle,
          class: this.headerClass,
          props: {
            dark: this.isDark,
            disable: this.disable,
            dense: this.dense,
            insetLevel: this.headerInsetLevel
          }
        };

        if (this.isClickable === true) {
          var evtProp = this.hasRouterLink === true ? 'nativeOn' : 'on';

          data.props.clickable = true;
          data[evtProp] = Object.assign({}, this.$listeners,
            {click: this.__onHeaderClick});

          this.hasRouterLink === true && Object.assign(
            data.props,
            this.routerLinkProps
          );
        }

        return h(QItem, data, child)
      },

      __getContent: function __getContent (h) {
        var this$1 = this;

        var node = [
          this.__getHeader(h),

          h(QSlideTransition, {
            props: { duration: this.duration },
            on: cache(this, 'slide', {
              show: function () { this$1.$emit('after-show'); },
              hide: function () { this$1.$emit('after-hide'); }
            })
          }, [
            h('div', {
              staticClass: 'q-expansion-item__content relative-position',
              style: this.contentStyle,
              directives: [{ name: 'show', value: this.showing }]
            }, slot(this, 'default'))
          ])
        ];

        if (this.expandSeparator) {
          node.push(
            h(QSeparator, {
              staticClass: 'q-expansion-item__border q-expansion-item__border--top absolute-top',
              props: { dark: this.isDark }
            }),
            h(QSeparator, {
              staticClass: 'q-expansion-item__border q-expansion-item__border--bottom absolute-bottom',
              props: { dark: this.isDark }
            })
          );
        }

        return node
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-expansion-item q-item-type',
        class: this.classes
      }, [
        h(
          'div',
          { staticClass: 'q-expansion-item__container relative-position' },
          this.__getContent(h)
        )
      ])
    },

    created: function created () {
      this.group !== void 0 && this.$root.$on(eventName, this.__eventHandler);
    },

    beforeDestroy: function beforeDestroy () {
      this.group !== void 0 && this.$root.$off(eventName, this.__eventHandler);
    }
  });

  var labelPositions = ['top', 'right', 'bottom', 'left'];

  var FabMixin = {
    props: {
      type: {
        type: String,
        default: 'a'
      },
      outline: Boolean,
      push: Boolean,
      flat: Boolean,
      unelevated: Boolean,
      color: String,
      textColor: String,
      glossy: Boolean,

      square: Boolean,

      label: {
        type: [ String, Number ],
        default: ''
      },
      labelPosition: {
        type: String,
        default: 'right',
        validator: function (v) { return labelPositions.includes(v); }
      },
      externalLabel: Boolean,
      hideLabel: Boolean,
      labelClass: [ Array, String, Object ],
      labelStyle: [ Array, String, Object ],

      disable: Boolean
    },

    computed: {
      formClass: function formClass () {
        return ("q-fab--form-" + (this.square === true ? 'square' : 'rounded'))
      },

      stacked: function stacked () {
        return this.externalLabel === false && ['top', 'bottom'].includes(this.labelPosition)
      },

      labelProps: function labelProps () {
        if (this.externalLabel === true) {
          var hideLabel = this.hideLabel === null
            ? this.showing === false
            : this.hideLabel;

          return {
            action: 'push',
            data: {
              staticClass: "q-fab__label q-tooltip--style q-fab__label--external" +
                " q-fab__label--external-" + (this.labelPosition) +
                (hideLabel === true ? ' q-fab__label--external-hidden' : ''),
              style: this.labelStyle,
              class: this.labelClass
            }
          }
        }

        return {
          action: [ 'left', 'top' ].includes(this.labelPosition)
            ? 'unshift'
            : 'push',
          data: {
            staticClass: "q-fab__label q-fab__label--internal q-fab__label--internal-" + (this.labelPosition) +
              (this.hideLabel === true ? ' q-fab__label--internal-hidden' : ''),
            style: this.labelStyle,
            class: this.labelClass
          }
        }
      }
    }
  };

  var directions$1 = ['up', 'right', 'down', 'left'];
  var alignValues$1 = [ 'left', 'center', 'right' ];

  var QFab = Vue.extend({
    name: 'QFab',

    mixins: [ FabMixin, ModelToggleMixin ],

    provide: function provide () {
      var this$1 = this;

      return {
        __qFabClose: function (evt) {
          this$1.hide(evt);

          if (this$1.$refs.trigger && this$1.$refs.trigger.$el) {
            this$1.$refs.trigger.$el.focus();
          }
        }
      }
    },

    props: {
      icon: String,
      activeIcon: String,

      hideLabel: {
        default: null
      },

      direction: {
        type: String,
        default: 'right',
        validator: function (v) { return directions$1.includes(v); }
      },

      persistent: Boolean,

      verticalActionsAlign: {
        type: String,
        default: 'center',
        validator: function (v) { return alignValues$1.includes(v); }
      }
    },

    data: function data () {
      return {
        showing: this.value === true
      }
    },

    computed: {
      hideOnRouteChange: function hideOnRouteChange () {
        return this.persistent !== true
      },

      classes: function classes () {
        return "q-fab--align-" + (this.verticalActionsAlign) + " " + (this.formClass) +
          (this.showing === true ? ' q-fab--opened' : '')
      }
    },

    render: function render (h) {
      var child = [
        h('div', { staticClass: 'q-fab__icon-holder' }, [
          h(QIcon, {
            staticClass: 'q-fab__icon absolute-full',
            props: { name: this.icon || this.$q.iconSet.fab.icon }
          }),
          h(QIcon, {
            staticClass: 'q-fab__active-icon absolute-full',
            props: { name: this.activeIcon || this.$q.iconSet.fab.activeIcon }
          })
        ])
      ];

      this.label !== '' && child[this.labelProps.action](
        h('div', this.labelProps.data, [ this.label ])
      );

      return h('div', {
        staticClass: 'q-fab z-fab row inline justify-center',
        class: this.classes,
        on: this.$listeners
      }, [
        h('div', {
          staticClass: 'q-fab__actions flex no-wrap inline',
          class: ("q-fab__actions--" + (this.direction))
        }, slot(this, 'default')),

        h(QBtn, {
          ref: 'trigger',
          class: this.formClass,
          props: Object.assign({}, this.$props,
            {noWrap: true,
            stack: this.stacked,
            align: void 0,
            icon: void 0,
            label: void 0,
            noCaps: true,
            fab: true}),
          on: cache(this, 'tog', {
            click: this.toggle
          })
        }, mergeSlot(child, this, 'tooltip'))
      ])
    }
  });

  var anchorMap = {
    start: 'self-end',
    center: 'self-center',
    end: 'self-start'
  };

  var anchorValues = Object.keys(anchorMap);

  var QFabAction = Vue.extend({
    name: 'QFabAction',

    mixins: [ FabMixin ],

    props: {
      icon: {
        type: String,
        required: true
      },

      anchor: {
        type: String,
        validator: function (v) { return anchorValues.includes(v); }
      },

      to: [String, Object],
      replace: Boolean
    },

    inject: {
      __qFabClose: {
        default: function default$1 () {
          console.error('QFabAction needs to be child of QFab');
        }
      }
    },

    computed: {
      classes: function classes () {
        var align = anchorMap[this.anchor];
        return this.formClass + (align !== void 0 ? (" " + align) : '')
      }
    },

    methods: {
      click: function click (e) {
        this.__qFabClose();
        this.$emit('click', e);
      }
    },

    render: function render (h) {
      var child = [
        h(QIcon, {
          props: { name: this.icon }
        })
      ];

      this.label !== '' && child[this.labelProps.action](
        h('div', this.labelProps.data, [ this.label ])
      );

      return h(QBtn, {
        class: this.classes,
        props: Object.assign({}, this.$props,
          {noWrap: true,
          stack: this.stacked,
          icon: void 0,
          label: void 0,
          noCaps: true,
          fabMini: true}),
        on: Object.assign({}, this.$listeners,
          {click: this.click})
      }, mergeSlot(child, this, 'default'))
    }
  });

  var QFile = Vue.extend({
    name: 'QFile',

    mixins: [ QField, FileMixin, FormFieldMixin, FileValueMixin ],

    props: {
      /* SSR does not know about File & FileList */
      value: isSSR === true
        ? {}
        : [ File, FileList, Array ],

      useChips: Boolean,
      displayValue: [ String, Number ],
      maxFiles: [ Number, String ],

      tabindex: {
        type: [ String, Number ],
        default: 0
      },

      counterLabel: Function,

      inputClass: [ Array, String, Object ],
      inputStyle: [ Array, String, Object ]
    },

    data: function data () {
      return {
        dnd: false
      }
    },

    computed: {
      innerValue: function innerValue () {
        return Object(this.value) === this.value
          ? ('length' in this.value ? Array.from(this.value) : [ this.value ])
          : []
      },

      selectedString: function selectedString () {
        return this.innerValue
          .map(function (file) { return file.name; })
          .join(', ')
      },

      totalSize: function totalSize () {
        return humanStorageSize(
          this.innerValue.reduce(function (acc, file) { return acc + file.size; }, 0)
        )
      },

      counterProps: function counterProps () {
        return {
          totalSize: this.totalSize,
          filesNumber: this.innerValue.length,
          maxFiles: this.maxFiles
        }
      },

      computedCounter: function computedCounter () {
        if (this.counterLabel !== void 0) {
          return this.counterLabel(this.counterProps)
        }

        var max = this.maxFiles;
        return ("" + (this.innerValue.length) + (max !== void 0 ? ' / ' + max : '') + " (" + (this.totalSize) + ")")
      }
    },

    methods: {
      removeAtIndex: function removeAtIndex (index) {
        var files = this.innerValue.slice();
        files.splice(index, 1);
        this.__emitValue(files);
      },

      removeFile: function removeFile (file) {
        var index = this.innerValue.findIndex(file);
        if (index > -1) {
          this.removeAtIndex(index);
        }
      },

      __emitValue: function __emitValue (files) {
        this.$emit('input', this.multiple === true ? files : files[0]);
      },

      __onKeyup: function __onKeyup (e) {
        // only on ENTER
        e.keyCode === 13 && this.pickFiles(e);
      },

      __getFileInput: function __getFileInput () {
        return this.$refs.input
      },

      __addFiles: function __addFiles (e, fileList) {
        var files = this.__processFiles(e, fileList);

        files !== void 0 && this.__emitValue(
          this.maxFiles !== void 0
            ? files.slice(0, parseInt(this.maxFiles, 10))
            : files
        );
      },

      __getControl: function __getControl (h) {
        var data = {
          ref: 'target',
          staticClass: 'q-field__native row items-center cursor-pointer',
          attrs: {
            tabindex: this.tabindex
          }
        };

        if (this.editable === true) {
          data.on = cache(this, 'native', {
            dragover: this.__onDragOver,
            keyup: this.__onKeyup
          });
        }

        return h('div', data, [ this.__getInput(h) ].concat(this.__getSelection(h)))
      },

      __getControlChild: function __getControlChild (h) {
        return this.__getDnd(h, 'file')
      },

      __getSelection: function __getSelection (h) {
        var this$1 = this;

        if (this.$scopedSlots.file !== void 0) {
          return this.innerValue.map(function (file, index) { return this$1.$scopedSlots.file({ index: index, file: file, ref: this$1 }); })
        }

        if (this.$scopedSlots.selected !== void 0) {
          return this.$scopedSlots.selected({ files: this.innerValue, ref: this })
        }

        if (this.useChips === true) {
          return this.innerValue.map(function (file, i) { return h(QChip, {
            key: 'file-' + i,
            props: {
              removable: this$1.editable,
              dense: true,
              textColor: this$1.color,
              tabindex: this$1.tabindex
            },
            on: cache(this$1, 'rem#' + i, {
              remove: function () { this$1.removeAtIndex(i); }
            })
          }, [
            h('span', {
              staticClass: 'ellipsis',
              domProps: {
                textContent: file.name
              }
            })
          ]); })
        }

        return [
          h('div', {
            style: this.inputStyle,
            class: this.inputClass,
            domProps: {
              textContent: this.displayValue !== void 0
                ? this.displayValue
                : this.selectedString
            }
          })
        ]
      },

      __getInput: function __getInput (h) {
        var data = {
          ref: 'input',
          staticClass: 'q-field__input fit absolute-full cursor-pointer',
          attrs: Object.assign({}, {tabindex: -1,
            type: 'file',
            title: '', // try to remove default tooltip,
            accept: this.accept,
            name: this.nameProp},
            this.$attrs,
            {id: this.targetUid,
            disabled: this.editable !== true}),
          domProps: this.formDomProps,
          on: cache(this, 'input', {
            change: this.__addFiles
          })
        };

        if (this.multiple === true) {
          data.attrs.multiple = true;
        }

        return h('input', data)
      }
    },

    created: function created () {
      this.fieldClass = 'q-file q-field--auto-height';
      this.type = 'file'; // necessary for QField's clearable
    }
  });

  var QFooter = Vue.extend({
    name: 'QFooter',

    inject: {
      layout: {
        default: function default$1 () {
          console.error('QFooter needs to be child of QLayout');
        }
      }
    },

    props: {
      value: {
        type: Boolean,
        default: true
      },
      reveal: Boolean,
      bordered: Boolean,
      elevated: Boolean,

      heightHint: {
        type: [String, Number],
        default: 50
      }
    },

    data: function data () {
      return {
        size: parseInt(this.heightHint, 10),
        revealed: true,
        windowHeight: onSSR || this.layout.container ? 0 : window.innerHeight
      }
    },

    watch: {
      value: function value (val) {
        this.__update('space', val);
        this.__updateLocal('revealed', true);
        this.layout.__animate();
      },

      offset: function offset (val) {
        this.__update('offset', val);
      },

      reveal: function reveal (val) {
        val === false && this.__updateLocal('revealed', this.value);
      },

      revealed: function revealed (val) {
        this.layout.__animate();
        this.$emit('reveal', val);
      },

      'layout.scroll': function layout_scroll () {
        this.__updateRevealed();
      },

      'layout.height': function layout_height () {
        this.__updateRevealed();
      },

      size: function size () {
        this.__updateRevealed();
      },

      '$q.screen.height': function $q_screen_height (val) {
        this.layout.container !== true && this.__updateLocal('windowHeight', val);
      }
    },

    computed: {
      fixed: function fixed () {
        return this.reveal === true ||
          this.layout.view.indexOf('F') > -1 ||
          this.layout.container === true
      },

      containerHeight: function containerHeight () {
        return this.layout.container === true
          ? this.layout.containerHeight
          : this.windowHeight
      },

      offset: function offset () {
        if (this.value !== true) {
          return 0
        }
        if (this.fixed === true) {
          return this.revealed === true ? this.size : 0
        }
        var offset = this.layout.scroll.position + this.containerHeight + this.size - this.layout.height;
        return offset > 0 ? offset : 0
      },

      classes: function classes () {
        return (
          (this.fixed === true ? 'fixed' : 'absolute') + '-bottom') +
          (this.value === true || this.fixed === true ? '' : ' hidden') +
          (this.bordered === true ? ' q-footer--bordered' : '') +
          (
            this.value !== true || (this.fixed === true && this.revealed !== true)
              ? ' q-footer--hidden'
              : ''
          )
      },

      style: function style () {
        var
          view = this.layout.rows.bottom,
          css = {};

        if (view[0] === 'l' && this.layout.left.space === true) {
          css[this.$q.lang.rtl === true ? 'right' : 'left'] = (this.layout.left.size) + "px";
        }
        if (view[2] === 'r' && this.layout.right.space === true) {
          css[this.$q.lang.rtl === true ? 'left' : 'right'] = (this.layout.right.size) + "px";
        }

        return css
      }
    },

    render: function render (h) {
      var child = [
        h(QResizeObserver, {
          props: { debounce: 0 },
          on: cache(this, 'resize', { resize: this.__onResize })
        })
      ];

      this.elevated === true && child.push(
        h('div', {
          staticClass: 'q-layout__shadow absolute-full overflow-hidden no-pointer-events'
        })
      );

      return h('footer', {
        staticClass: 'q-footer q-layout__section--marginal',
        class: this.classes,
        style: this.style,
        on: Object.assign({}, this.$listeners,
          {input: stop})
      }, mergeSlot(child, this, 'default'))
    },

    created: function created () {
      this.layout.instances.footer = this;
      this.value === true && this.__update('size', this.size);
      this.__update('space', this.value);
      this.__update('offset', this.offset);
    },

    beforeDestroy: function beforeDestroy () {
      if (this.layout.instances.footer === this) {
        this.layout.instances.footer = void 0;
        this.__update('size', 0);
        this.__update('offset', 0);
        this.__update('space', false);
      }
    },

    methods: {
      __onResize: function __onResize (ref) {
        var height = ref.height;

        this.__updateLocal('size', height);
        this.__update('size', height);
      },

      __update: function __update (prop, val) {
        if (this.layout.footer[prop] !== val) {
          this.layout.footer[prop] = val;
        }
      },

      __updateLocal: function __updateLocal (prop, val) {
        if (this[prop] !== val) {
          this[prop] = val;
        }
      },

      __updateRevealed: function __updateRevealed () {
        if (this.reveal !== true) { return }

        var ref = this.layout.scroll;
        var direction = ref.direction;
        var position = ref.position;
        var inflexionPosition = ref.inflexionPosition;

        this.__updateLocal('revealed', (
          direction === 'up' ||
          position - inflexionPosition < 100 ||
          this.layout.height - this.containerHeight - position - this.size < 300
        ));
      }
    }
  });

  var QForm = Vue.extend({
    name: 'QForm',

    props: {
      autofocus: Boolean,
      noErrorFocus: Boolean,
      noResetFocus: Boolean,
      greedy: Boolean
    },

    mounted: function mounted () {
      this.validateIndex = 0;
      this.autofocus === true && this.focus();
    },

    methods: {
      validate: function validate (shouldFocus) {
        var this$1 = this;

        var promises = [];
        var focus = typeof shouldFocus === 'boolean'
          ? shouldFocus
          : this.noErrorFocus !== true;

        this.validateIndex++;

        var components = getAllChildren(this);
        var emit = function (res) {
          this$1.$emit('validation-' + (res === true ? 'success' : 'error'));
        };

        var loop = function ( i ) {
          var comp = components[i];

          if (typeof comp.validate === 'function') {
            var valid = comp.validate();

            if (typeof valid.then === 'function') {
              promises.push(
                valid.then(
                  function (valid) { return ({ valid: valid, comp: comp }); },
                  function (error) { return ({ valid: false, comp: comp, error: error }); }
                )
              );
            }
            else if (valid !== true) {
              if (this$1.greedy === false) {
                emit(false);

                if (focus === true && typeof comp.focus === 'function') {
                  comp.focus();
                }

                return { v: Promise.resolve(false) }
              }

              promises.push({ valid: false, comp: comp });
            }
          }
        };

        for (var i = 0; i < components.length; i++) {
          var returned = loop( i );

          if ( returned ) return returned.v;
        }

        if (promises.length === 0) {
          emit(true);
          return Promise.resolve(true)
        }

        var index = this.validateIndex;

        return Promise.all(promises).then(
          function (res) {
            if (index === this$1.validateIndex) {
              var errors = res.filter(function (r) { return r.valid !== true; });

              if (errors.length === 0) {
                emit(true);
                return true
              }

              emit(false);
              var ref = errors[0];
              var valid = ref.valid;
              var comp = ref.comp;

              if (
                focus === true &&
                valid !== true &&
                typeof comp.focus === 'function'
              ) {
                comp.focus();
              }

              return false
            }
          }
        )
      },

      resetValidation: function resetValidation () {
        this.validateIndex++;

        getAllChildren(this).forEach(function (comp) {
          if (typeof comp.resetValidation === 'function') {
            comp.resetValidation();
          }
        });
      },

      submit: function submit (evt) {
        var this$1 = this;

        evt !== void 0 && stopAndPrevent(evt);

        this.validate().then(function (val) {
          if (val === true) {
            if (this$1.$listeners.submit !== void 0) {
              this$1.$emit('submit', evt);
            }
            else if (evt !== void 0 && evt.target !== void 0 && typeof evt.target.submit === 'function') {
              evt.target.submit();
            }
          }
        });
      },

      reset: function reset (evt) {
        var this$1 = this;

        evt !== void 0 && stopAndPrevent(evt);

        this.$emit('reset');

        this.$nextTick(function () { // allow userland to reset values before
          this$1.resetValidation();
          if (this$1.autofocus === true && this$1.noResetFocus !== true) {
            this$1.focus();
          }
        });
      },

      focus: function focus () {
        var target = this.$el.querySelector('[autofocus], [data-autofocus]') ||
          [].find.call(this.$el.querySelectorAll('[tabindex]'), function (el) { return el.tabIndex > -1; });

        target !== null && target !== void 0 && target.focus();
      }
    },

    render: function render (h) {
      return h('form', {
        staticClass: 'q-form',
        on: Object.assign({}, this.$listeners,
          {submit: this.submit,
          reset: this.reset})
      }, slot(this, 'default'))
    }
  });

  var QHeader = Vue.extend({
    name: 'QHeader',

    inject: {
      layout: {
        default: function default$1 () {
          console.error('QHeader needs to be child of QLayout');
        }
      }
    },

    props: {
      value: {
        type: Boolean,
        default: true
      },
      reveal: Boolean,
      revealOffset: {
        type: Number,
        default: 250
      },
      bordered: Boolean,
      elevated: Boolean,

      heightHint: {
        type: [String, Number],
        default: 50
      }
    },

    data: function data () {
      return {
        size: parseInt(this.heightHint, 10),
        revealed: true
      }
    },

    watch: {
      value: function value (val) {
        this.__update('space', val);
        this.__updateLocal('revealed', true);
        this.layout.__animate();
      },

      offset: function offset (val) {
        this.__update('offset', val);
      },

      reveal: function reveal (val) {
        val === false && this.__updateLocal('revealed', this.value);
      },

      revealed: function revealed (val) {
        this.layout.__animate();
        this.$emit('reveal', val);
      },

      'layout.scroll': function layout_scroll (scroll) {
        this.reveal === true && this.__updateLocal('revealed',
          scroll.direction === 'up' ||
          scroll.position <= this.revealOffset ||
          scroll.position - scroll.inflexionPosition < 100
        );
      }
    },

    computed: {
      fixed: function fixed () {
        return this.reveal === true ||
          this.layout.view.indexOf('H') > -1 ||
          this.layout.container === true
      },

      offset: function offset () {
        if (this.value !== true) {
          return 0
        }
        if (this.fixed === true) {
          return this.revealed === true ? this.size : 0
        }
        var offset = this.size - this.layout.scroll.position;
        return offset > 0 ? offset : 0
      },

      classes: function classes () {
        return (
          this.fixed === true ? 'fixed' : 'absolute') + '-top' +
          (this.bordered === true ? ' q-header--bordered' : '') +
          (
            this.value !== true || (this.fixed === true && this.revealed !== true)
              ? ' q-header--hidden'
              : ''
          )
      },

      style: function style () {
        var
          view = this.layout.rows.top,
          css = {};

        if (view[0] === 'l' && this.layout.left.space === true) {
          css[this.$q.lang.rtl === true ? 'right' : 'left'] = (this.layout.left.size) + "px";
        }
        if (view[2] === 'r' && this.layout.right.space === true) {
          css[this.$q.lang.rtl === true ? 'left' : 'right'] = (this.layout.right.size) + "px";
        }

        return css
      }
    },

    render: function render (h) {
      var child = mergeSlot([
        h(QResizeObserver, {
          props: { debounce: 0 },
          on: cache(this, 'resize', { resize: this.__onResize })
        })
      ], this, 'default');

      this.elevated === true && child.push(
        h('div', {
          staticClass: 'q-layout__shadow absolute-full overflow-hidden no-pointer-events'
        })
      );

      return h('header', {
        staticClass: 'q-header q-layout__section--marginal',
        class: this.classes,
        style: this.style,
        on: Object.assign({}, this.$listeners,
          {input: stop})
      }, child)
    },

    created: function created () {
      this.layout.instances.header = this;
      this.value === true && this.__update('size', this.size);
      this.__update('space', this.value);
      this.__update('offset', this.offset);
    },

    beforeDestroy: function beforeDestroy () {
      if (this.layout.instances.header === this) {
        this.layout.instances.header = void 0;
        this.__update('size', 0);
        this.__update('offset', 0);
        this.__update('space', false);
      }
    },

    methods: {
      __onResize: function __onResize (ref) {
        var height = ref.height;

        this.__updateLocal('size', height);
        this.__update('size', height);
      },

      __update: function __update (prop, val) {
        if (this.layout.header[prop] !== val) {
          this.layout.header[prop] = val;
        }
      },

      __updateLocal: function __updateLocal (prop, val) {
        if (this[prop] !== val) {
          this[prop] = val;
        }
      }
    }
  });

  var RatioMixin = {
    props: {
      ratio: [ String, Number ]
    },

    computed: {
      ratioStyle: function ratioStyle () {
        var ratio = this.ratio || this.naturalRatio;

        if (ratio !== void 0) {
          return { paddingBottom: ((100 / ratio) + "%") }
        }
      }
    }
  };

  var QImg = Vue.extend({
    name: 'QImg',

    mixins: [ RatioMixin ],

    props: {
      src: String,
      srcset: String,
      sizes: String,
      alt: String,
      width: String,
      height: String,

      placeholderSrc: String,

      basic: Boolean,
      contain: Boolean,
      position: {
        type: String,
        default: '50% 50%'
      },

      transition: {
        type: String,
        default: 'fade'
      },

      imgClass: [ Array, String, Object ],
      imgStyle: Object,

      nativeContextMenu: Boolean,

      noDefaultSpinner: Boolean,
      spinnerColor: String,
      spinnerSize: String
    },

    data: function data () {
      return {
        currentSrc: '',
        image: null,
        isLoading: !!this.src,
        hasError: false,
        naturalRatio: void 0
      }
    },

    watch: {
      src: function src () {
        this.__load();
      },

      srcset: function srcset (val) {
        this.__updateWatcher(val);
      }
    },

    computed: {
      url: function url () {
        return this.currentSrc || this.placeholderSrc || void 0
      },

      attrs: function attrs () {
        var att = { role: 'img' };
        if (this.alt !== void 0) {
          att['aria-label'] = this.alt;
        }
        return att
      },

      imgContainerStyle: function imgContainerStyle () {
        return Object.assign(
          {
            backgroundSize: this.contain === true ? 'contain' : 'cover',
            backgroundPosition: this.position
          },
          this.imgStyle,
          { backgroundImage: ("url(\"" + (this.url) + "\")") })
      },

      style: function style () {
        return {
          width: this.width,
          height: this.height
        }
      },

      classes: function classes () {
        return 'q-img overflow-hidden' +
          (this.nativeContextMenu === true ? ' q-img--menu' : '')
      }
    },

    methods: {
      __onLoad: function __onLoad (img) {
        this.isLoading = false;
        this.hasError = false;
        this.__computeRatio(img);
        this.__updateSrc();
        this.__updateWatcher(this.srcset);
        this.$emit('load', this.currentSrc);
      },

      __onError: function __onError (err) {
        clearTimeout(this.ratioTimer);
        this.isLoading = false;
        this.hasError = true;
        this.currentSrc = '';
        this.$emit('error', err);
      },

      __updateSrc: function __updateSrc () {
        if (this.image !== void 0 && this.isLoading === false) {
          var src = this.image.currentSrc || this.image.src;
          if (this.currentSrc !== src) {
            this.currentSrc = src;
          }
        }
      },

      __updateWatcher: function __updateWatcher (srcset) {
        if (srcset) {
          if (this.unwatch === void 0) {
            this.unwatch = this.$watch('$q.screen.width', this.__updateSrc);
          }
        }
        else if (this.unwatch !== void 0) {
          this.unwatch();
          this.unwatch = void 0;
        }
      },

      __load: function __load () {
        var this$1 = this;

        clearTimeout(this.ratioTimer);
        this.hasError = false;

        if (!this.src) {
          this.isLoading = false;
          this.image = void 0;
          this.currentSrc = '';
          return
        }

        this.isLoading = true;

        var img = new Image();
        this.image = img;

        img.onerror = function (err) {
          // if we are still rendering same image
          if (this$1.image === img && this$1.destroyed !== true) {
            this$1.__onError(err);
          }
        };

        img.onload = function () {
          if (this$1.destroyed === true) {
            return
          }

          // if we are still rendering same image
          if (this$1.image === img) {
            if (img.decode !== void 0) {
              img
                .decode()
                .catch(function (err) {
                  if (this$1.image === img && this$1.destroyed !== true) {
                    this$1.__onError(err);
                  }
                })
                .then(function () {
                  if (this$1.image === img && this$1.destroyed !== true) {
                    this$1.__onLoad(img);
                  }
                });
            }
            else {
              this$1.__onLoad(img);
            }
          }
        };

        img.src = this.src;

        if (this.srcset) {
          img.srcset = this.srcset;
        }

        if (this.sizes !== void 0) {
          img.sizes = this.sizes;
        }
        else {
          Object.assign(img, {
            height: this.height,
            width: this.width
          });
        }
      },

      __computeRatio: function __computeRatio (img) {
        var this$1 = this;

        var naturalHeight = img.naturalHeight;
        var naturalWidth = img.naturalWidth;

        if (naturalHeight || naturalWidth) {
          this.naturalRatio = naturalHeight === 0
            ? 1
            : naturalWidth / naturalHeight;
        }
        else {
          this.ratioTimer = setTimeout(function () {
            if (this$1.image === img && this$1.destroyed !== true) {
              this$1.__computeRatio(img);
            }
          }, 100);
        }
      },

      __getImage: function __getImage (h) {
        var nativeImg = this.nativeContextMenu === true
          ? [
            h('img', {
              staticClass: 'absolute-full fit',
              attrs: { src: this.url }
            })
          ]
          : void 0;

        var content = this.url !== void 0
          ? h('div', {
            key: this.url,
            staticClass: 'q-img__image absolute-full',
            class: this.imgClass,
            style: this.imgContainerStyle
          }, nativeImg)
          : null;

        return this.basic === true
          ? content
          : h('transition', {
            props: { name: 'q-transition--' + this.transition }
          }, [ content ])
      },

      __getContent: function __getContent (h) {
        var slotVm = slot(this, this.hasError === true ? 'error' : 'default');

        if (this.basic === true) {
          return h('div', {
            key: 'content',
            staticClass: 'q-img__content absolute-full'
          }, slotVm)
        }

        var content = this.isLoading === true
          ? h('div', {
            key: 'placeholder',
            staticClass: 'q-img__loading absolute-full flex flex-center'
          }, this.$scopedSlots.loading !== void 0
            ? this.$scopedSlots.loading()
            : (
              this.noDefaultSpinner === false
                ? [
                  h(QSpinner, {
                    props: {
                      color: this.spinnerColor,
                      size: this.spinnerSize
                    }
                  })
                ]
                : void 0
            )
          )
          : h('div', {
            key: 'content',
            staticClass: 'q-img__content absolute-full'
          }, slotVm);

        return h('transition', {
          props: { name: 'q-transition--fade' }
        }, [ content ])
      }
    },

    render: function render (h) {
      return h('div', {
        class: this.classes,
        style: this.style,
        attrs: this.attrs,
        on: this.$listeners
      }, [
        h('div', { style: this.ratioStyle }),
        this.__getImage(h),
        this.__getContent(h)
      ])
    },

    beforeMount: function beforeMount () {
      if (this.placeholderSrc !== void 0 && this.ratio === void 0) {
        var img = new Image();
        img.src = this.placeholderSrc;
        this.__computeRatio(img);
      }
      this.isLoading === true && this.__load();
    },

    beforeDestroy: function beforeDestroy () {
      this.destroyed = true;
      clearTimeout(this.ratioTimer);
      this.unwatch !== void 0 && this.unwatch();
    }
  });

  var QInfiniteScroll = Vue.extend({
    name: 'QInfiniteScroll',

    props: {
      offset: {
        type: Number,
        default: 500
      },
      debounce: {
        type: [String, Number],
        default: 100
      },
      scrollTarget: {
        default: void 0
      },
      disable: Boolean,
      reverse: Boolean
    },

    data: function data () {
      return {
        index: 0,
        fetching: false,
        working: true
      }
    },

    watch: {
      disable: function disable (val) {
        if (val === true) {
          this.stop();
        }
        else {
          this.resume();
        }
      },

      scrollTarget: function scrollTarget () {
        this.updateScrollTarget();
      },

      debounce: function debounce (val) {
        this.__setDebounce(val);
      }
    },

    methods: {
      poll: function poll () {
        if (this.disable === true || this.fetching === true || this.working === false) {
          return
        }

        var
          scrollHeight = getScrollHeight(this.scrollContainer),
          scrollPosition = getScrollPosition(this.scrollContainer),
          containerHeight = height(this.scrollContainer);

        if (this.reverse === false) {
          if (scrollPosition + containerHeight + this.offset >= scrollHeight) {
            this.trigger();
          }
        }
        else {
          if (scrollPosition < this.offset) {
            this.trigger();
          }
        }
      },

      trigger: function trigger () {
        var this$1 = this;

        if (this.disable === true || this.fetching === true || this.working === false) {
          return
        }

        this.index++;
        this.fetching = true;

        var heightBefore = getScrollHeight(this.scrollContainer);

        this.$emit('load', this.index, function (stop) {
          if (this$1.working === true) {
            this$1.fetching = false;
            this$1.$nextTick(function () {
              if (this$1.reverse === true) {
                var
                  heightAfter = getScrollHeight(this$1.scrollContainer),
                  scrollPosition = getScrollPosition(this$1.scrollContainer),
                  heightDifference = heightAfter - heightBefore;

                setScrollPosition(this$1.scrollContainer, scrollPosition + heightDifference);
              }

              if (stop === true) {
                this$1.stop();
              }
              else {
                this$1.$el.closest('body') && this$1.poll();
              }
            });
          }
        });
      },

      reset: function reset () {
        this.index = 0;
      },

      resume: function resume () {
        if (this.working === false) {
          this.working = true;
          this.scrollContainer.addEventListener('scroll', this.poll, listenOpts.passive);
        }
        this.immediatePoll();
      },

      stop: function stop () {
        if (this.working === true) {
          this.working = false;
          this.fetching = false;
          this.scrollContainer.removeEventListener('scroll', this.poll, listenOpts.passive);
        }
      },

      updateScrollTarget: function updateScrollTarget () {
        if (this.scrollContainer && this.working === true) {
          this.scrollContainer.removeEventListener('scroll', this.poll, listenOpts.passive);
        }

        this.scrollContainer = getScrollTarget(this.$el, this.scrollTarget);

        if (this.working === true) {
          this.scrollContainer.addEventListener('scroll', this.poll, listenOpts.passive);
        }
      },

      __setDebounce: function __setDebounce (val) {
        val = parseInt(val, 10);
        if (val <= 0) {
          this.poll = this.immediatePoll;
        }
        else {
          this.poll = debounce(this.immediatePoll, isNaN(val) === true ? 100 : val);
        }
      }
    },

    mounted: function mounted () {
      this.immediatePoll = this.poll;
      this.__setDebounce(this.debounce);

      this.updateScrollTarget();
      this.immediatePoll();

      if (this.reverse === true) {
        var
          scrollHeight = getScrollHeight(this.scrollContainer),
          containerHeight = height(this.scrollContainer);

        setScrollPosition(this.scrollContainer, scrollHeight - containerHeight);
      }
    },

    beforeDestroy: function beforeDestroy () {
      if (this.working === true) {
        this.scrollContainer.removeEventListener('scroll', this.poll, listenOpts.passive);
      }
    },

    render: function render (h) {
      var child = uniqueSlot(this, 'default', []);

      if (this.disable !== true && this.working === true) {
        child[this.reverse === false ? 'push' : 'unshift'](
          h('div', {
            staticClass: 'q-infinite-scroll__loading',
            class: this.fetching === true ? '' : 'invisible'
          }, slot(this, 'loading'))
        );
      }

      return h('div', {
        staticClass: 'q-infinite-scroll',
        on: this.$listeners
      }, child)
    }
  });

  var QInnerLoading = Vue.extend({
    name: 'QInnerLoading',

    mixins: [ DarkMixin, TransitionMixin ],

    props: {
      showing: Boolean,
      color: String,

      size: {
        type: [String, Number],
        default: 42
      }
    },

    render: function render (h) {
      var child = this.showing === true
        ? [
          h('div',
            {
              staticClass: 'q-inner-loading absolute-full column flex-center',
              class: this.isDark === true ? 'q-inner-loading--dark' : null,
              on: this.$listeners
            },
            this.$scopedSlots.default !== void 0
              ? this.$scopedSlots.default()
              : [
                h(QSpinner, {
                  props: {
                    size: this.size,
                    color: this.color
                  }
                })
              ]
          )
        ]
        : void 0;

      return h('transition', {
        props: {
          name: this.transition,
          appear: true
        }
      }, child)
    }
  });

  var defaultCfg = {
    threshold: 0,
    root: null,
    rootMargin: '0px'
  };

  function update (el, ctx, ref) {
    var modifiers = ref.modifiers;
    var value = ref.value;

    ctx.once = modifiers.once;

    var handler, cfg, changed;

    if (typeof value === 'function') {
      handler = value;
      cfg = defaultCfg;
      changed = ctx.cfg === void 0;
    }
    else {
      handler = value.handler;
      cfg = Object.assign({}, defaultCfg, value.cfg);
      changed = ctx.cfg === void 0 || isDeepEqual(ctx.cfg, cfg) === false;
    }

    if (ctx.handler !== handler) {
      ctx.handler = handler;
    }

    if (changed === true) {
      ctx.cfg = cfg;
      ctx.observer !== void 0 && ctx.observer.unobserve(el);

      ctx.observer = new IntersectionObserver(function (ref) {
        var entry = ref[0];

        if (typeof ctx.handler === 'function' && el.__vue__._inactive !== true) {
          if (entry.rootBounds === null) {
            ctx.observer.unobserve(el);
            ctx.observer.observe(el);

            return
          }

          var res = ctx.handler(entry, ctx.observer);

          if (
            res === false ||
            (ctx.once === true && entry.isIntersecting === true)
          ) {
            destroy(el);
          }
        }
      }, cfg);

      ctx.observer.observe(el);
    }
  }

  function destroy (el) {
    var ctx = el.__qvisible;

    if (ctx !== void 0) {
      ctx.observer !== void 0 && ctx.observer.unobserve(el);
      delete el.__qvisible;
    }
  }

  var Intersection = {
    name: 'intersection',

    inserted: function inserted (el, binding) {
      var ctx = {};
      update(el, ctx, binding);
      el.__qvisible = ctx;
    },

    update: function update$1 (el, binding) {
      var ctx = el.__qvisible;
      ctx !== void 0 && update(el, ctx, binding);
    },

    unbind: destroy
  };

  var QIntersection = Vue.extend({
    name: 'QIntersection',

    mixins: [ TagMixin ],

    directives: {
      Intersection: Intersection
    },

    props: {
      once: Boolean,
      transition: String,

      ssrPrerender: Boolean,

      margin: String,
      threshold: [ Number, Array ],

      disable: Boolean
    },

    data: function data () {
      return {
        showing: onSSR === true ? this.ssrPrerender : false
      }
    },

    computed: {
      value: function value () {
        return this.margin !== void 0 || this.threshold !== void 0
          ? {
            handler: this.__trigger,
            cfg: {
              rootMargin: this.margin,
              threshold: this.threshold
            }
          }
          : this.__trigger
      },

      directives: function directives () {
        if (this.disable !== true && (onSSR !== true || this.once !== true || this.ssrPrerender !== true)) {
          return [{
            name: 'intersection',
            value: this.value,
            modifiers: {
              once: this.once
            }
          }]
        }
      }
    },

    methods: {
      __trigger: function __trigger (entry) {
        if (this.showing !== entry.isIntersecting) {
          this.showing = entry.isIntersecting;

          if (this.$listeners.visibility !== void 0) {
            this.$emit('visibility', this.showing);
          }
        }
      }
    },

    render: function render (h) {
      var content = this.showing === true
        ? [ h('div', { key: 'content' }, slot(this, 'default')) ]
        : void 0;

      return h(this.tag, {
        staticClass: 'q-intersection',
        on: this.$listeners,
        directives: this.directives
      }, this.transition
        ? [
          h('transition', {
            props: { name: 'q-transition--' + this.transition }
          }, content)
        ]
        : content
      )
    }
  });

  // PGDOWN, LEFT, DOWN, PGUP, RIGHT, UP
  var keyCodes$1 = [34, 37, 40, 33, 39, 38];

  var QKnob = Vue.extend({
    name: 'QKnob',

    mixins: [
      { props: QCircularProgress.options.props },
      FormMixin
    ],

    directives: {
      TouchPan: TouchPan
    },

    props: {
      step: {
        type: Number,
        default: 1,
        validator: function (v) { return v >= 0; }
      },

      tabindex: {
        type: [Number, String],
        default: 0
      },

      disable: Boolean,
      readonly: Boolean
    },

    data: function data () {
      return {
        model: this.value,
        dragging: false
      }
    },

    watch: {
      value: function value (value$1) {
        if (value$1 < this.min) {
          this.model = this.min;
        }
        else if (value$1 > this.max) {
          this.model = this.max;
        }
        else {
          if (value$1 !== this.model) {
            this.model = value$1;
          }
          return
        }

        if (this.model !== this.value) {
          this.$emit('input', this.model);
          this.$emit('change', this.model);
        }
      }
    },

    computed: {
      classes: function classes () {
        return {
          disabled: this.disable,
          'q-knob--editable': this.editable
        }
      },

      editable: function editable () {
        return !this.disable && !this.readonly
      },

      decimals: function decimals () {
        return (String(this.step).trim('0').split('.')[1] || '').length
      },

      computedStep: function computedStep () {
        return this.step === 0 ? 1 : this.step
      },

      events: function events () {
        return this.$q.platform.is.mobile === true
          ? { click: this.__click }
          : {
            mousedown: this.__activate,
            click: this.__click,
            keydown: this.__keydown,
            keyup: this.__keyup
          }
      },

      attrs: function attrs () {
        var attrs = {
          role: 'slider',
          'aria-valuemin': this.min,
          'aria-valuemax': this.max,
          'aria-valuenow': this.value
        };

        if (this.editable === true) {
          attrs.tabindex = this.tabindex;
        }
        else {
          attrs[("aria-" + (this.disable === true ? 'disabled' : 'readonly'))] = '';
        }

        return attrs
      }
    },

    methods: {
      __updateCenterPosition: function __updateCenterPosition () {
        var ref = this.$el.getBoundingClientRect();
        var top = ref.top;
        var left = ref.left;
        var width = ref.width;
        var height = ref.height;
        this.centerPosition = {
          top: top + height / 2,
          left: left + width / 2
        };
      },

      __pan: function __pan (event) {
        if (event.isFinal) {
          this.__updatePosition(event.evt, true);
          this.dragging = false;
        }
        else if (event.isFirst) {
          this.__updateCenterPosition();
          this.dragging = true;
          this.__updatePosition(event.evt);
        }
        else {
          this.__updatePosition(event.evt);
        }
      },

      __click: function __click (evt) {
        this.__updateCenterPosition();
        this.__updatePosition(evt, true);
      },

      __keydown: function __keydown (evt) {
        if (!keyCodes$1.includes(evt.keyCode)) {
          return
        }

        stopAndPrevent(evt);

        var
          step = ([34, 33].includes(evt.keyCode) ? 10 : 1) * this.computedStep,
          offset = [34, 37, 40].includes(evt.keyCode) ? -step : step;

        this.model = between(
          parseFloat((this.model + offset).toFixed(this.decimals)),
          this.min,
          this.max
        );

        this.__updateValue();
      },

      __keyup: function __keyup (evt) {
        if (keyCodes$1.includes(evt.keyCode)) {
          this.__updateValue(true);
        }
      },

      __activate: function __activate (evt) {
        this.__updateCenterPosition();
        this.__updatePosition(evt);
        this.__updateValue();
      },

      __updatePosition: function __updatePosition (evt, change) {
        var
          center = this.centerPosition,
          pos = position(evt),
          height = Math.abs(pos.top - center.top),
          distance = Math.sqrt(
            Math.pow( height, 2 ) +
            Math.pow( Math.abs(pos.left - center.left), 2 )
          );

        var angle = Math.asin(height / distance) * (180 / Math.PI);

        if (pos.top < center.top) {
          angle = center.left < pos.left ? 90 - angle : 270 + angle;
        }
        else {
          angle = center.left < pos.left ? angle + 90 : 270 - angle;
        }

        if (this.angle) {
          angle = normalizeToInterval(angle - this.angle, 0, 360);
        }

        if (this.$q.lang.rtl === true) {
          angle = 360 - angle;
        }

        var model = this.min + (angle / 360) * (this.max - this.min);

        if (this.step !== 0) {
          var
            step = this.computedStep,
            modulo = model % step;

          model = model - modulo +
            (Math.abs(modulo) >= step / 2 ? (modulo < 0 ? -1 : 1) * step : 0);

          model = parseFloat(model.toFixed(this.decimals));
        }

        model = between(model, this.min, this.max);

        this.$emit('drag-value', model);

        if (this.model !== model) {
          this.model = model;
        }

        this.__updateValue(change);
      },

      __updateValue: function __updateValue (change) {
        this.value !== this.model && this.$emit('input', this.model);
        change === true && this.$emit('change', this.model);
      },

      __getNameInput: function __getNameInput () {
        return this.$createElement('input', { attrs: this.formAttrs })
      }
    },

    render: function render (h) {
      var data = {
        staticClass: 'q-knob non-selectable',
        class: this.classes,

        attrs: this.attrs,

        props: Object.assign({}, this.$props,
          {value: this.model,
          instantFeedback: this.dragging})
      };

      if (this.editable === true) {
        data.on = this.events;
        data.directives = cache(this, 'dir', [{
          name: 'touch-pan',
          value: this.__pan,
          modifiers: {
            prevent: true,
            stop: true,
            mouse: true
          }
        }]);

        if (this.name !== void 0) {
          data.scopedSlots = {
            internal: this.__getNameInput
          };
        }
      }

      return h(QCircularProgress, data, slot(this, 'default'))
    }
  });

  var passive$1 = listenOpts.passive;

  var QScrollObserver = Vue.extend({
    name: 'QScrollObserver',

    props: {
      debounce: [ String, Number ],
      horizontal: Boolean,

      scrollTarget: {
        default: void 0
      }
    },

    render: noop, // eslint-disable-line

    data: function data () {
      return {
        pos: 0,
        dir: this.horizontal === true ? 'right' : 'down',
        dirChanged: false,
        dirChangePos: 0
      }
    },

    watch: {
      scrollTarget: function scrollTarget () {
        this.__unconfigureScrollTarget();
        this.__configureScrollTarget();
      }
    },

    methods: {
      getPosition: function getPosition () {
        return {
          position: this.pos,
          direction: this.dir,
          directionChanged: this.dirChanged,
          inflexionPosition: this.dirChangePos
        }
      },

      trigger: function trigger (immediately) {
        if (immediately === true || this.debounce === 0 || this.debounce === '0') {
          this.__emit();
        }
        else if (!this.timer) {
          this.timer = this.debounce
            ? setTimeout(this.__emit, this.debounce)
            : requestAnimationFrame(this.__emit);
        }
      },

      __emit: function __emit () {
        var fn = this.horizontal === true
          ? getHorizontalScrollPosition
          : getScrollPosition;

        var
          pos = Math.max(0, fn(this.__scrollTarget)),
          delta = pos - this.pos,
          dir = this.horizontal === true
            ? delta < 0 ? 'left' : 'right'
            : delta < 0 ? 'up' : 'down';

        this.dirChanged = this.dir !== dir;

        if (this.dirChanged) {
          this.dir = dir;
          this.dirChangePos = this.pos;
        }

        this.timer = null;
        this.pos = pos;
        this.$emit('scroll', this.getPosition());
      },

      __configureScrollTarget: function __configureScrollTarget () {
        this.__scrollTarget = getScrollTarget(this.$el.parentNode, this.scrollTarget);
        this.__scrollTarget.addEventListener('scroll', this.trigger, passive$1);
        this.trigger(true);
      },

      __unconfigureScrollTarget: function __unconfigureScrollTarget () {
        if (this.__scrollTarget !== void 0) {
          this.__scrollTarget.removeEventListener('scroll', this.trigger, passive$1);
          this.__scrollTarget = void 0;
        }
      }
    },

    mounted: function mounted () {
      this.__configureScrollTarget();
    },

    beforeDestroy: function beforeDestroy () {
      clearTimeout(this.timer);
      cancelAnimationFrame(this.timer);
      this.__unconfigureScrollTarget();
    }
  });

  var QLayout = Vue.extend({
    name: 'QLayout',

    provide: function provide () {
      return {
        layout: this
      }
    },

    props: {
      container: Boolean,
      view: {
        type: String,
        default: 'hhh lpr fff',
        validator: function (v) { return /^(h|l)h(h|r) lpr (f|l)f(f|r)$/.test(v.toLowerCase()); }
      }
    },

    data: function data () {
      return {
        // page related
        height: this.$q.screen.height,
        width: this.container === true ? 0 : this.$q.screen.width,

        // container only prop
        containerHeight: 0,
        scrollbarWidth: onSSR === true ? 0 : getScrollbarWidth(),

        header: {
          size: 0,
          offset: 0,
          space: false
        },
        right: {
          size: 300,
          offset: 0,
          space: false
        },
        footer: {
          size: 0,
          offset: 0,
          space: false
        },
        left: {
          size: 300,
          offset: 0,
          space: false
        },

        scroll: {
          position: 0,
          direction: 'down'
        }
      }
    },

    computed: {
      rows: function rows () {
        var rows = this.view.toLowerCase().split(' ');
        return {
          top: rows[0].split(''),
          middle: rows[1].split(''),
          bottom: rows[2].split('')
        }
      },

      style: function style () {
        return this.container === true
          ? null
          : { minHeight: this.$q.screen.height + 'px' }
      },

      // used by container only
      targetStyle: function targetStyle () {
        var obj;

        if (this.scrollbarWidth !== 0) {
          return ( obj = {}, obj[this.$q.lang.rtl === true ? 'left' : 'right'] = ((this.scrollbarWidth) + "px"), obj )
        }
      },

      targetChildStyle: function targetChildStyle () {
        var obj;

        if (this.scrollbarWidth !== 0) {
          return ( obj = {}, obj[this.$q.lang.rtl === true ? 'right' : 'left'] = 0, obj[this.$q.lang.rtl === true ? 'left' : 'right'] = ("-" + (this.scrollbarWidth) + "px"), obj.width = ("calc(100% + " + (this.scrollbarWidth) + "px)"), obj )
        }
      },

      totalWidth: function totalWidth () {
        return this.width + this.scrollbarWidth
      },

      classes: function classes () {
        return 'q-layout q-layout--' +
          (this.container === true ? 'containerized' : 'standard')
      }
    },

    created: function created () {
      this.instances = {};
    },

    render: function render (h) {
      var layout = h('div', {
        class: this.classes,
        style: this.style,
        on: this.$listeners
      }, mergeSlot([
        h(QScrollObserver, {
          on: cache(this, 'scroll', { scroll: this.__onPageScroll })
        }),

        h(QResizeObserver, {
          on: cache(this, 'resizeOut', { resize: this.__onPageResize })
        })
      ], this, 'default'));

      return this.container === true
        ? h('div', {
          staticClass: 'q-layout-container overflow-hidden'
        }, [
          h(QResizeObserver, {
            on: cache(this, 'resizeIn', { resize: this.__onContainerResize })
          }),
          h('div', {
            staticClass: 'absolute-full',
            style: this.targetStyle
          }, [
            h('div', {
              staticClass: 'scroll',
              style: this.targetChildStyle
            }, [ layout ])
          ])
        ])
        : layout
    },

    methods: {
      __animate: function __animate () {
        var this$1 = this;

        if (this.timer !== void 0) {
          clearTimeout(this.timer);
        }
        else {
          document.body.classList.add('q-body--layout-animate');
        }
        this.timer = setTimeout(function () {
          document.body.classList.remove('q-body--layout-animate');
          this$1.timer = void 0;
        }, 150);
      },

      __onPageScroll: function __onPageScroll (data) {
        this.scroll = data;
        this.$listeners.scroll !== void 0 && this.$emit('scroll', data);
      },

      __onPageResize: function __onPageResize (ref) {
        var height = ref.height;
        var width = ref.width;

        var resized = false;

        if (this.height !== height) {
          resized = true;
          this.height = height;
          if (this.$listeners['scroll-height'] !== void 0) {
            this.$emit('scroll-height', height);
          }
          this.__updateScrollbarWidth();
        }
        if (this.width !== width) {
          resized = true;
          this.width = width;
        }

        if (resized === true && this.$listeners.resize !== void 0) {
          this.$emit('resize', { height: height, width: width });
        }
      },

      __onContainerResize: function __onContainerResize (ref) {
        var height = ref.height;

        if (this.containerHeight !== height) {
          this.containerHeight = height;
          this.__updateScrollbarWidth();
        }
      },

      __updateScrollbarWidth: function __updateScrollbarWidth () {
        if (this.container === true) {
          var width = this.height > this.containerHeight
            ? getScrollbarWidth()
            : 0;

          if (this.scrollbarWidth !== width) {
            this.scrollbarWidth = width;
          }
        }
      }
    }
  });

  var QMarkupTable = Vue.extend({
    name: 'QMarkupTable',

    mixins: [ DarkMixin ],

    props: {
      dense: Boolean,
      flat: Boolean,
      bordered: Boolean,
      square: Boolean,
      separator: {
        type: String,
        default: 'horizontal',
        validator: function (v) { return ['horizontal', 'vertical', 'cell', 'none'].includes(v); }
      },
      wrapCells: Boolean
    },

    computed: {
      classes: function classes () {
        return "q-table--" + (this.separator) + "-separator" +
          (this.isDark === true ? " q-table--dark q-table__card--dark q-dark" : '') +
          (this.dense === true ? " q-table--dense" : '') +
          (this.flat === true ? " q-table--flat" : '') +
          (this.bordered === true ? " q-table--bordered" : '') +
          (this.square === true ? " q-table--square" : '') +
          (this.wrapCells === false ? " q-table--no-wrap" : '')
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-markup-table q-table__container q-table__card',
        class: this.classes,
        on: this.$listeners
      }, [
        h('table', { staticClass: 'q-table' }, slot(this, 'default'))
      ])
    }
  });

  var QNoSsr = Vue.extend({
    name: 'QNoSsr',

    mixins: [ CanRenderMixin, TagMixin ],

    props: {
      placeholder: String
    },

    render: function render (h) {
      var data = {
        on: this.$listeners
      };

      if (this.canRender === true) {
        var node$1 = slot(this, 'default');
        return node$1 === void 0
          ? node$1
          : (node$1.length > 1 ? h(this.tag, data, node$1) : node$1[0])
      }

      data.staticClass = 'q-no-ssr-placeholder';

      var node = slot(this, 'placeholder');
      if (node !== void 0) {
        return node.length > 1
          ? h(this.tag, data, node)
          : node[0]
      }

      if (this.placeholder !== void 0) {
        return h(this.tag, data, [
          this.placeholder
        ])
      }
    }
  });

  var QRadio = Vue.extend({
    name: 'QRadio',

    mixins: [ DarkMixin, OptionSizeMixin, FormMixin, RefocusTargetMixin ],

    props: {
      value: {
        required: true
      },
      val: {
        required: true
      },

      label: String,
      leftLabel: Boolean,

      color: String,
      keepColor: Boolean,
      dense: Boolean,

      disable: Boolean,
      tabindex: [String, Number]
    },

    computed: {
      isTrue: function isTrue () {
        return this.value === this.val
      },

      classes: function classes () {
        return 'q-radio cursor-pointer no-outline row inline no-wrap items-center' +
          (this.disable === true ? ' disabled' : '') +
          (this.isDark === true ? ' q-radio--dark' : '') +
          (this.dense === true ? ' q-radio--dense' : '') +
          (this.leftLabel === true ? ' reverse' : '')
      },

      innerClass: function innerClass () {
        var color = this.color !== void 0 && (
          this.keepColor === true ||
          this.isTrue === true
        )
          ? (" text-" + (this.color))
          : '';

        return ("q-radio__inner--" + (this.isTrue === true ? 'truthy' : 'falsy') + color)
      },

      computedTabindex: function computedTabindex () {
        return this.disable === true ? -1 : this.tabindex || 0
      },

      formAttrs: function formAttrs () {
        var prop = { type: 'radio' };

        this.name !== void 0 && Object.assign(prop, {
          name: this.name,
          value: this.val
        });

        return prop
      },

      formDomProps: function formDomProps () {
        if (this.name !== void 0 && this.isTrue === true) {
          return { checked: true }
        }
      },

      attrs: function attrs () {
        var attrs = {
          tabindex: this.computedTabindex,
          role: 'radio',
          'aria-label': this.label,
          'aria-checked': this.isTrue === true ? 'true' : 'false'
        };

        if (this.disable === true) {
          attrs['aria-disabled'] = '';
        }

        return attrs
      }
    },

    methods: {
      set: function set (e) {
        if (e !== void 0) {
          stopAndPrevent(e);
          this.__refocusTarget(e);
        }

        if (this.disable !== true && this.isTrue !== true) {
          this.$emit('input', this.val);
        }
      }
    },

    render: function render (h) {
      var this$1 = this;

      var content = [
        h('svg', {
          staticClass: 'q-radio__bg absolute',
          attrs: { focusable: 'false' /* needed for IE11 */, viewBox: '0 0 24 24' }
        }, [
          h('path', {
            attrs: {
              d: 'M12,22a10,10 0 0 1 -10,-10a10,10 0 0 1 10,-10a10,10 0 0 1 10,10a10,10 0 0 1 -10,10m0,-22a12,12 0 0 0 -12,12a12,12 0 0 0 12,12a12,12 0 0 0 12,-12a12,12 0 0 0 -12,-12'
            }
          }),

          h('path', {
            staticClass: 'q-radio__check',
            attrs: {
              d: 'M12,6a6,6 0 0 0 -6,6a6,6 0 0 0 6,6a6,6 0 0 0 6,-6a6,6 0 0 0 -6,-6'
            }
          })
        ])
      ];

      this.disable !== true && this.__injectFormInput(
        content,
        'unshift',
        'q-radio__native q-ma-none q-pa-none invisible'
      );

      var child = [
        h('div', {
          staticClass: 'q-radio__inner relative-position no-pointer-events',
          class: this.innerClass,
          style: this.sizeStyle
        }, content)
      ];

      if (this.__refocusTargetEl !== void 0) {
        child.push(this.__refocusTargetEl);
      }

      var label = this.label !== void 0
        ? mergeSlot([ this.label ], this, 'default')
        : slot(this, 'default');

      label !== void 0 && child.push(
        h('div', {
          staticClass: 'q-radio__label q-anchor--skip'
        }, label)
      );

      return h('div', {
        class: this.classes,
        attrs: this.attrs,
        on: cache(this, 'inpExt', {
          click: this.set,
          keydown: function (e) {
            if (e.keyCode === 13 || e.keyCode === 32) {
              stopAndPrevent(e);
            }
          },
          keyup: function (e) {
            if (e.keyCode === 13 || e.keyCode === 32) {
              this$1.set(e);
            }
          }
        })
      }, child)
    }
  });

  var QToggle = Vue.extend({
    name: 'QToggle',

    mixins: [ CheckboxMixin ],

    props: {
      icon: String,
      checkedIcon: String,
      uncheckedIcon: String,
      indeterminateIcon: String,

      iconColor: String
    },

    computed: {
      computedIcon: function computedIcon () {
        return (
          this.isTrue === true
            ? this.checkedIcon
            : (this.isIndeterminate === true ? this.indeterminateIcon : this.uncheckedIcon)
        ) || this.icon
      },

      computedIconColor: function computedIconColor () {
        if (this.isTrue === true) {
          return this.iconColor
        }
      }
    },

    methods: {
      __getInner: function __getInner (h) {
        return [
          h('div', { staticClass: 'q-toggle__track' }),

          h('div', {
            staticClass: 'q-toggle__thumb absolute flex flex-center no-wrap'
          }, this.computedIcon !== void 0
            ? [
              h(QIcon, {
                props: {
                  name: this.computedIcon,
                  color: this.computedIconColor
                }
              })
            ]
            : void 0
          )
        ]
      }
    },

    created: function created () {
      this.type = 'toggle';
    }
  });

  var components = {
    radio: QRadio,
    checkbox: QCheckbox,
    toggle: QToggle
  };

  var typeValues = Object.keys(components);

  var QOptionGroup = Vue.extend({
    name: 'QOptionGroup',

    mixins: [ DarkMixin ],

    props: {
      value: {
        required: true
      },
      options: {
        type: Array,
        validator: function validator (opts) {
          return opts.every(function (opt) { return 'value' in opt && 'label' in opt; })
        }
      },

      name: String,

      type: {
        default: 'radio',
        validator: function (v) { return typeValues.includes(v); }
      },

      color: String,
      keepColor: Boolean,
      dense: Boolean,

      size: String,

      leftLabel: Boolean,
      inline: Boolean,
      disable: Boolean
    },

    computed: {
      component: function component () {
        return components[this.type]
      },

      model: function model () {
        return Array.isArray(this.value)
          ? this.value.slice()
          : this.value
      },

      classes: function classes () {
        return 'q-option-group q-gutter-x-sm' +
          (this.inline === true ? ' q-option-group--inline' : '')
      },

      attrs: function attrs () {
        if (this.type === 'radio') {
          var attrs = {
            role: 'radiogroup'
          };

          if (this.disable === true) {
            attrs['aria-disabled'] = '';
          }

          return attrs
        }
      }
    },

    methods: {
      __update: function __update (value) {
        this.$emit('input', value);
      }
    },

    created: function created () {
      var isArray = Array.isArray(this.value);

      if (this.type === 'radio') {
        if (isArray) {
          console.error('q-option-group: model should not be array');
        }
      }
      else if (isArray === false) {
        console.error('q-option-group: model should be array in your case');
      }
    },

    render: function render (h) {
      var this$1 = this;

      return h('div', {
        class: this.classes,
        attrs: this.attrs,
        on: this.$listeners
      }, this.options.map(function (opt) { return h('div', [
        h(this$1.component, {
          props: {
            value: this$1.value,
            val: opt.value,
            name: this$1.name || opt.name,
            disable: this$1.disable || opt.disable,
            label: opt.label,
            leftLabel: this$1.leftLabel || opt.leftLabel,
            color: opt.color || this$1.color,
            checkedIcon: opt.checkedIcon,
            uncheckedIcon: opt.uncheckedIcon,
            dark: opt.dark || this$1.isDark,
            size: opt.size || this$1.size,
            dense: this$1.dense,
            keepColor: opt.keepColor || this$1.keepColor
          },
          on: cache(this$1, 'inp', {
            input: this$1.__update
          })
        })
      ]); }))
    }
  });

  var QPage = Vue.extend({
    name: 'QPage',

    inject: {
      pageContainer: {
        default: function default$1 () {
          console.error('QPage needs to be child of QPageContainer');
        }
      },
      layout: {}
    },

    props: {
      padding: Boolean,
      styleFn: Function
    },

    computed: {
      style: function style () {
        var offset =
          (this.layout.header.space === true ? this.layout.header.size : 0) +
          (this.layout.footer.space === true ? this.layout.footer.size : 0);

        if (typeof this.styleFn === 'function') {
          var height = this.layout.container === true
            ? this.layout.containerHeight
            : this.$q.screen.height;

          return this.styleFn(offset, height)
        }

        return {
          minHeight: this.layout.container === true
            ? (this.layout.containerHeight - offset) + 'px'
            : (
              this.$q.screen.height === 0
                ? ("calc(100vh - " + offset + "px)")
                : (this.$q.screen.height - offset) + 'px'
            )
        }
      },

      classes: function classes () {
        if (this.padding === true) {
          return 'q-layout-padding'
        }
      }
    },

    render: function render (h) {
      return h('main', {
        staticClass: 'q-page',
        style: this.style,
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QPageContainer = Vue.extend({
    name: 'QPageContainer',

    inject: {
      layout: {
        default: function default$1 () {
          console.error('QPageContainer needs to be child of QLayout');
        }
      }
    },

    provide: {
      pageContainer: true
    },

    computed: {
      style: function style () {
        var css = {};

        if (this.layout.header.space === true) {
          css.paddingTop = (this.layout.header.size) + "px";
        }
        if (this.layout.right.space === true) {
          css[("padding" + (this.$q.lang.rtl === true ? 'Left' : 'Right'))] = (this.layout.right.size) + "px";
        }
        if (this.layout.footer.space === true) {
          css.paddingBottom = (this.layout.footer.size) + "px";
        }
        if (this.layout.left.space === true) {
          css[("padding" + (this.$q.lang.rtl === true ? 'Right' : 'Left'))] = (this.layout.left.size) + "px";
        }

        return css
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-page-container',
        style: this.style,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QPageSticky = Vue.extend({
    name: 'QPageSticky',

    inject: {
      layout: {
        default: function default$1 () {
          console.error('QPageSticky needs to be child of QLayout');
        }
      }
    },

    props: {
      position: {
        type: String,
        default: 'bottom-right',
        validator: function (v) { return [
          'top-right', 'top-left',
          'bottom-right', 'bottom-left',
          'top', 'right', 'bottom', 'left'
        ].includes(v); }
      },
      offset: {
        type: Array,
        validator: function (v) { return v.length === 2; }
      },
      expand: Boolean
    },

    computed: {
      attach: function attach () {
        var pos = this.position;

        return {
          top: pos.indexOf('top') > -1,
          right: pos.indexOf('right') > -1,
          bottom: pos.indexOf('bottom') > -1,
          left: pos.indexOf('left') > -1,
          vertical: pos === 'top' || pos === 'bottom',
          horizontal: pos === 'left' || pos === 'right'
        }
      },

      top: function top () {
        return this.layout.header.offset
      },

      right: function right () {
        return this.layout.right.offset
      },

      bottom: function bottom () {
        return this.layout.footer.offset
      },

      left: function left () {
        return this.layout.left.offset
      },

      style: function style () {
        var
          posX = 0,
          posY = 0;

        var
          attach = this.attach,
          dir = this.$q.lang.rtl === true ? -1 : 1;

        if (attach.top === true && this.top !== 0) {
          posY = (this.top) + "px";
        }
        else if (attach.bottom === true && this.bottom !== 0) {
          posY = (-this.bottom) + "px";
        }

        if (attach.left === true && this.left !== 0) {
          posX = (dir * this.left) + "px";
        }
        else if (attach.right === true && this.right !== 0) {
          posX = (-dir * this.right) + "px";
        }

        var css = { transform: ("translate(" + posX + ", " + posY + ")") };

        if (this.offset) {
          css.margin = (this.offset[1]) + "px " + (this.offset[0]) + "px";
        }

        if (attach.vertical === true) {
          if (this.left !== 0) {
            css[this.$q.lang.rtl === true ? 'right' : 'left'] = (this.left) + "px";
          }
          if (this.right !== 0) {
            css[this.$q.lang.rtl === true ? 'left' : 'right'] = (this.right) + "px";
          }
        }
        else if (attach.horizontal === true) {
          if (this.top !== 0) {
            css.top = (this.top) + "px";
          }
          if (this.bottom !== 0) {
            css.bottom = (this.bottom) + "px";
          }
        }

        return css
      },

      classes: function classes () {
        return ("fixed-" + (this.position) + " q-page-sticky--" + (this.expand === true ? 'expand' : 'shrink'))
      }
    },

    render: function render (h) {
      var content = slot(this, 'default');

      return h('div', {
        staticClass: 'q-page-sticky row flex-center',
        class: this.classes,
        style: this.style,
        on: this.$listeners
      },
      this.expand === true
        ? content
        : [ h('div', content) ]
      )
    }
  });

  var QPageScroller = Vue.extend({
    name: 'QPageScroller',

    mixins: [ QPageSticky ],

    props: {
      scrollOffset: {
        type: Number,
        default: 1000
      },

      reverse: Boolean,

      duration: {
        type: Number,
        default: 300
      },

      offset: {
        default: function () { return [18, 18]; }
      }
    },

    inject: {
      layout: {
        default: function default$1 () {
          console.error('QPageScroller needs to be used within a QLayout');
        }
      }
    },

    data: function data () {
      return {
        showing: this.__isVisible()
      }
    },

    computed: {
      height: function height () {
        return this.layout.container === true
          ? this.layout.containerHeight
          : this.layout.height
      }
    },

    watch: {
      'layout.scroll.position': function layout_scroll_position () {
        this.__updateVisibility();
      },

      reverse: {
        handler: function handler (val) {
          if (val === true) {
            if (this.heightWatcher === void 0) {
              this.heightWatcher = this.$watch('height', this.__updateVisibility);
            }
          }
          else if (this.heightWatcher !== void 0) {
            this.__cleanup();
          }
        },
        immediate: true
      }
    },

    methods: {
      __isVisible: function __isVisible () {
        return this.reverse === true
          ? this.height - this.layout.scroll.position > this.scrollOffset
          : this.layout.scroll.position > this.scrollOffset
      },

      __onClick: function __onClick (e) {
        var target = this.layout.container === true
          ? getScrollTarget(this.$el)
          : getScrollTarget(this.layout.$el);

        setScrollPosition(target, this.reverse === true ? this.layout.height : 0, this.duration);
        this.$emit('click', e);
      },

      __updateVisibility: function __updateVisibility () {
        var newVal = this.__isVisible();
        if (this.showing !== newVal) {
          this.showing = newVal;
        }
      },

      __cleanup: function __cleanup () {
        this.heightWatcher();
        this.heightWatcher = void 0;
      }
    },

    render: function render (h) {
      return h('transition', {
        props: { name: 'q-transition--fade' }
      },
      this.showing === true
        ? [
          h('div', {
            staticClass: 'q-page-scroller',
            on: Object.assign({}, this.$listeners,
              {click: this.__onClick})
          }, [
            QPageSticky.options.render.call(this, h)
          ])
        ]
        : null
      )
    },

    beforeDestroy: function beforeDestroy () {
      this.heightWatcher !== void 0 && this.__cleanup();
    }
  });

  var QPagination = Vue.extend({
    name: 'QPagination',

    mixins: [ DarkMixin ],

    props: {
      value: {
        type: Number,
        required: true
      },
      min: {
        type: Number,
        default: 1
      },
      max: {
        type: Number,
        required: true
      },

      color: {
        type: String,
        default: 'primary'
      },
      textColor: String,

      inputStyle: [Array, String, Object],
      inputClass: [Array, String, Object],

      size: String,

      disable: Boolean,

      input: Boolean,

      iconPrev: String,
      iconNext: String,
      iconFirst: String,
      iconLast: String,

      toFn: Function,

      boundaryLinks: {
        type: Boolean,
        default: null
      },
      boundaryNumbers: {
        type: Boolean,
        default: null
      },
      directionLinks: {
        type: Boolean,
        default: null
      },
      ellipses: {
        type: Boolean,
        default: null
      },
      maxPages: {
        type: Number,
        default: 0,
        validator: function (v) { return v >= 0; }
      }
    },

    data: function data () {
      return {
        newPage: null
      }
    },

    watch: {
      min: function min () {
        this.model = this.value;
      },

      max: function max () {
        this.model = this.value;
      }
    },

    computed: {
      model: {
        get: function get () {
          return this.value
        },
        set: function set (val) {
          val = parseInt(val, 10);
          if (this.disable || isNaN(val) || val === 0) {
            return
          }
          var value = between(val, this.min, this.max);
          this.$emit('input', value);
        }
      },

      inputPlaceholder: function inputPlaceholder () {
        return this.model + ' / ' + this.max
      },

      __boundaryLinks: function __boundaryLinks () {
        return this.__getBool(this.boundaryLinks, this.input)
      },

      __boundaryNumbers: function __boundaryNumbers () {
        return this.__getBool(this.boundaryNumbers, !this.input)
      },

      __directionLinks: function __directionLinks () {
        return this.__getBool(this.directionLinks, this.input)
      },

      __ellipses: function __ellipses () {
        return this.__getBool(this.ellipses, !this.input)
      },

      icons: function icons () {
        var ico = [
          this.iconFirst || this.$q.iconSet.pagination.first,
          this.iconPrev || this.$q.iconSet.pagination.prev,
          this.iconNext || this.$q.iconSet.pagination.next,
          this.iconLast || this.$q.iconSet.pagination.last
        ];
        return this.$q.lang.rtl === true ? ico.reverse() : ico
      },

      attrs: function attrs () {
        if (this.disable === true) {
          return {
            'aria-disabled': ''
          }
        }
      }
    },

    methods: {
      set: function set (value) {
        this.model = value;
      },

      setByOffset: function setByOffset (offset) {
        this.model = this.model + offset;
      },

      __update: function __update () {
        this.model = this.newPage;
        this.newPage = null;
      },

      __getBool: function __getBool (val, otherwise) {
        return [true, false].includes(val)
          ? val
          : otherwise
      },

      __getBtn: function __getBtn (h, data, props, page) {
        var this$1 = this;

        data.props = Object.assign({}, {color: this.color,
          flat: true,
          size: this.size},
          props);

        if (page !== void 0) {
          if (this.toFn !== void 0) {
            data.props.to = this.toFn(page);
          }
          else {
            data.on = { click: function () { return this$1.set(page); } };
          }
        }

        return h(QBtn, data)
      }
    },

    render: function render (h) {
      var this$1 = this;

      var
        contentStart = [],
        contentEnd = [],
        contentMiddle = [];

      if (this.__boundaryLinks) {
        contentStart.push(this.__getBtn(h, {
          key: 'bls'
        }, {
          disable: this.disable || this.value <= this.min,
          icon: this.icons[0]
        }, this.min));
        contentEnd.unshift(this.__getBtn(h, {
          key: 'ble'
        }, {
          disable: this.disable || this.value >= this.max,
          icon: this.icons[3]
        }, this.max));
      }

      if (this.__directionLinks) {
        contentStart.push(this.__getBtn(h, {
          key: 'bdp'
        }, {
          disable: this.disable || this.value <= this.min,
          icon: this.icons[1]
        }, this.value - 1));
        contentEnd.unshift(this.__getBtn(h, {
          key: 'bdn'
        }, {
          disable: this.disable || this.value >= this.max,
          icon: this.icons[2]
        }, this.value + 1));
      }

      if (this.input === true) {
        contentMiddle.push(h(QInput, {
          staticClass: 'inline',
          style: {
            width: ((this.inputPlaceholder.length / 1.5) + "em")
          },
          props: {
            type: 'number',
            dense: true,
            value: this.newPage,
            disable: this.disable,
            dark: this.isDark,
            borderless: true,
            inputClass: this.inputClass,
            inputStyle: this.inputStyle
          },
          attrs: {
            placeholder: this.inputPlaceholder,
            min: this.min,
            max: this.max
          },
          on: cache(this, 'inp', {
            input: function (value) { this$1.newPage = value; },
            keyup: function (e) { isKeyCode(e, 13) === true && this$1.__update(); },
            blur: this.__update
          })
        }));
      }
      else { // is type select
        var
          maxPages = Math.max(
            this.maxPages,
            1 + (this.__ellipses ? 2 : 0) + (this.__boundaryNumbers ? 2 : 0)
          ),
          pgFrom = this.min,
          pgTo = this.max,
          ellipsesStart = false,
          ellipsesEnd = false,
          boundaryStart = false,
          boundaryEnd = false;

        if (this.maxPages && maxPages < (this.max - this.min + 1)) {
          maxPages = 1 + Math.floor(maxPages / 2) * 2;
          pgFrom = Math.max(this.min, Math.min(this.max - maxPages + 1, this.value - Math.floor(maxPages / 2)));
          pgTo = Math.min(this.max, pgFrom + maxPages - 1);
          if (this.__boundaryNumbers) {
            boundaryStart = true;
            pgFrom += 1;
          }
          if (this.__ellipses && pgFrom > (this.min + (this.__boundaryNumbers ? 1 : 0))) {
            ellipsesStart = true;
            pgFrom += 1;
          }
          if (this.__boundaryNumbers) {
            boundaryEnd = true;
            pgTo -= 1;
          }
          if (this.__ellipses && pgTo < (this.max - (this.__boundaryNumbers ? 1 : 0))) {
            ellipsesEnd = true;
            pgTo -= 1;
          }
        }
        var style = {
          minWidth: ((Math.max(2, String(this.max).length)) + "em")
        };
        if (boundaryStart) {
          var active = this.min === this.value;
          contentStart.push(this.__getBtn(h, {
            key: 'bns',
            style: style
          }, {
            disable: this.disable,
            flat: !active,
            textColor: active ? this.textColor : null,
            label: this.min,
            ripple: false
          }, this.min));
        }
        if (boundaryEnd) {
          var active$1 = this.max === this.value;
          contentEnd.unshift(this.__getBtn(h, {
            key: 'bne',
            style: style
          }, {
            disable: this.disable,
            flat: !active$1,
            textColor: active$1 ? this.textColor : null,
            label: this.max,
            ripple: false
          }, this.max));
        }
        if (ellipsesStart) {
          contentStart.push(this.__getBtn(h, {
            key: 'bes',
            style: style
          }, {
            disable: this.disable,
            label: '…'
          }, pgFrom - 1));
        }
        if (ellipsesEnd) {
          contentEnd.unshift(this.__getBtn(h, {
            key: 'bee',
            style: style
          }, {
            disable: this.disable,
            label: '…'
          }, pgTo + 1));
        }
        for (var i = pgFrom; i <= pgTo; i++) {
          var active$2 = i === this.value;
          contentMiddle.push(this.__getBtn(h, {
            key: ("bpg" + i),
            style: style
          }, {
            disable: this.disable,
            flat: !active$2,
            textColor: active$2 ? this.textColor : null,
            label: i,
            ripple: false
          }, i));
        }
      }

      return h('div', {
        staticClass: 'q-pagination row no-wrap items-center',
        class: { disabled: this.disable },
        attrs: this.attrs,
        on: this.$listeners
      }, [
        contentStart,

        h('div', {
          staticClass: 'row justify-center',
          on: this.input === true
            ? cache(this, 'stop', { input: stop })
            : null
        }, [
          contentMiddle
        ]),

        contentEnd
      ])
    }
  });

  function frameDebounce (fn) {
    var wait = false, frame, callArgs;

    function debounced (/* ...args */) {
      var this$1 = this;

      callArgs = arguments;
      if (wait === true) { return }

      wait = true;
      frame = requestAnimationFrame(function () {
        fn.apply(this$1, callArgs);
        callArgs = void 0;
        wait = false;
      });
    }

    debounced.cancel = function () {
      window.cancelAnimationFrame(frame);
      wait = false;
    };

    return debounced
  }

  var QParallax = Vue.extend({
    name: 'QParallax',

    props: {
      src: String,
      height: {
        type: Number,
        default: 500
      },
      speed: {
        type: Number,
        default: 1,
        validator: function (v) { return v >= 0 && v <= 1; }
      },

      scrollTarget: {
        default: void 0
      }
    },

    data: function data () {
      return {
        scrolling: false,
        percentScrolled: 0
      }
    },

    watch: {
      height: function height () {
        this.__updatePos();
      },

      scrollTarget: function scrollTarget () {
        this.__unconfigureScrollTarget();
        this.__configureScrollTarget();
      }
    },

    methods: {
      __update: function __update (percentage) {
        this.percentScrolled = percentage;
        this.$listeners.scroll !== void 0 && this.$emit('scroll', percentage);
      },

      __onResize: function __onResize () {
        if (this.__scrollTarget) {
          this.mediaHeight = this.media.naturalHeight || this.media.videoHeight || height(this.media);
          this.__updatePos();
        }
      },

      __updatePos: function __updatePos () {
        var containerTop, containerHeight, containerBottom, top, bottom;

        if (this.__scrollTarget === window) {
          containerTop = 0;
          containerHeight = window.innerHeight;
          containerBottom = containerHeight;
        }
        else {
          containerTop = offset(this.__scrollTarget).top;
          containerHeight = height(this.__scrollTarget);
          containerBottom = containerTop + containerHeight;
        }

        top = offset(this.$el).top;
        bottom = top + this.height;

        if (bottom > containerTop && top < containerBottom) {
          var percent = (containerBottom - top) / (this.height + containerHeight);
          this.__setPos((this.mediaHeight - this.height) * percent * this.speed);
          this.__update(percent);
        }
      },

      __setPos: function __setPos (offset) {
        // apply it immediately without any delay
        this.media.style.transform = "translate3D(-50%," + (Math.round(offset)) + "px, 0)";
      },

      __configureScrollTarget: function __configureScrollTarget () {
        this.__scrollTarget = getScrollTarget(this.$el, this.scrollTarget);
        this.__scrollTarget.addEventListener('scroll', this.__updatePos, listenOpts.passive);
        this.__onResize();
      },

      __unconfigureScrollTarget: function __unconfigureScrollTarget () {
        if (this.__scrollTarget !== void 0) {
          this.__scrollTarget.removeEventListener('scroll', this.__updatePos, listenOpts.passive);
          this.__scrollTarget = void 0;
        }
      }
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-parallax',
        style: { height: ((this.height) + "px") },
        on: this.$listeners
      }, [
        h('div', {
          ref: 'mediaParent',
          staticClass: 'q-parallax__media absolute-full'
        }, this.$scopedSlots.media !== void 0 ? this.$scopedSlots.media() : [
          h('img', {
            ref: 'media',
            attrs: {
              src: this.src
            }
          })
        ]),

        h(
          'div',
          { staticClass: 'q-parallax__content absolute-full column flex-center' },
          this.$scopedSlots.content !== void 0
            ? this.$scopedSlots.content({ percentScrolled: this.percentScrolled })
            : slot(this, 'default')
        )
      ])
    },

    beforeMount: function beforeMount () {
      this.__setPos = frameDebounce(this.__setPos);
    },

    mounted: function mounted () {
      this.__update = frameDebounce(this.__update);
      this.resizeHandler = frameDebounce(this.__onResize);

      this.media = this.$scopedSlots.media !== void 0
        ? this.$refs.mediaParent.children[0]
        : this.$refs.media;

      this.media.onload = this.media.onloadstart = this.media.loadedmetadata = this.__onResize;

      window.addEventListener('resize', this.resizeHandler, listenOpts.passive);

      this.__configureScrollTarget();
    },

    beforeDestroy: function beforeDestroy () {
      window.removeEventListener('resize', this.resizeHandler, listenOpts.passive);
      this.__unconfigureScrollTarget();
      this.media.onload = this.media.onloadstart = this.media.loadedmetadata = null;
    }
  });

  function clone$1 (data) {
    var s = JSON.stringify(data);
    if (s) {
      return JSON.parse(s)
    }
  }

  var QPopupEdit = Vue.extend({
    name: 'QPopupEdit',

    props: {
      value: {
        required: true
      },
      title: String,
      buttons: Boolean,
      labelSet: String,
      labelCancel: String,

      color: {
        type: String,
        default: 'primary'
      },
      validate: {
        type: Function,
        default: function () { return true; }
      },

      autoSave: Boolean,

      /* menu props overrides */
      cover: {
        type: Boolean,
        default: true
      },
      contentClass: String,
      /* end of menu props */

      disable: Boolean
    },

    data: function data () {
      return {
        initialValue: ''
      }
    },

    computed: {
      classes: function classes () {
        return 'q-popup-edit' +
          (this.contentClass !== void 0 ? (" " + (this.contentClass)) : '')
      },

      defaultSlotScope: function defaultSlotScope () {
        return {
          initialValue: this.initialValue,
          value: this.value,
          emitValue: this.__emitValue,
          validate: this.validate,
          set: this.set,
          cancel: this.cancel
        }
      }
    },

    methods: {
      set: function set () {
        if (this.__hasChanged() === true) {
          if (this.validate(this.value) === false) {
            return
          }
          this.$emit('save', this.value, this.initialValue);
        }
        this.__close();
      },

      cancel: function cancel () {
        if (this.__hasChanged() === true) {
          this.$emit('input', this.initialValue);
          this.$emit('cancel', this.value, this.initialValue);
        }
        this.__close();
      },

      __hasChanged: function __hasChanged () {
        return isDeepEqual(this.value, this.initialValue) === false
      },

      __emitValue: function __emitValue (val) {
        if (this.disable !== true) {
          this.$emit('input', val);
        }
      },

      __close: function __close () {
        this.validated = true;
        this.$refs.menu.showing === true && this.$refs.menu.hide();
      },

      __reposition: function __reposition () {
        var this$1 = this;

        this.$nextTick(function () {
          this$1.$refs.menu.updatePosition();
        });
      },

      __getContent: function __getContent (h) {
        var
          title = slot(this, 'title', this.title),
          child = this.$scopedSlots.default === void 0
            ? []
            : this.$scopedSlots.default(this.defaultSlotScope).slice();

        title && child.unshift(
          h('div', { staticClass: 'q-dialog__title q-mt-sm q-mb-sm' }, [ title ])
        );

        this.buttons === true && child.push(
          h('div', { staticClass: 'q-popup-edit__buttons row justify-center no-wrap' }, [
            h(QBtn, {
              props: {
                flat: true,
                color: this.color,
                label: this.labelCancel || this.$q.lang.label.cancel
              },
              on: cache(this, 'cancel', { click: this.cancel })
            }),
            h(QBtn, {
              props: {
                flat: true,
                color: this.color,
                label: this.labelSet || this.$q.lang.label.set
              },
              on: cache(this, 'ok', { click: this.set })
            })
          ])
        );

        return child
      }
    },

    render: function render (h) {
      var this$1 = this;

      if (this.disable === true) { return }

      return h(QMenu, {
        ref: 'menu',
        props: Object.assign({}, this.$attrs,
          {cover: this.cover,
          contentClass: this.classes}),
        on: cache(this, 'menu', {
          'before-show': function () {
            this$1.validated = false;
            this$1.initialValue = clone$1(this$1.value);
            this$1.watcher = this$1.$watch('value', this$1.__reposition);
            this$1.$emit('before-show');
          },
          show: function () {
            this$1.$emit('show');
          },
          'escape-key': this.cancel,
          'before-hide': function () {
            this$1.watcher();

            if (this$1.validated === false && this$1.__hasChanged() === true) {
              if (this$1.autoSave === true && this$1.validate(this$1.value) === true) {
                this$1.$emit('save', this$1.value, this$1.initialValue);
              }
              else {
                this$1.$emit('cancel', this$1.value, this$1.initialValue);
                this$1.$emit('input', this$1.initialValue);
              }
            }

            this$1.$emit('before-hide');
          },
          hide: function () {
            this$1.$emit('hide');
          },
          keyup: function (e) {
            isKeyCode(e, 13) === true && this$1.set();
          }
        })
      }, this.__getContent(h))
    }
  });

  var QPopupProxy = Vue.extend({
    name: 'QPopupProxy',

    mixins: [ AnchorMixin ],

    props: {
      breakpoint: {
        type: [String, Number],
        default: 450
      }
    },

    data: function data () {
      var breakpoint = parseInt(this.breakpoint, 10);
      return {
        type: this.$q.screen.width < breakpoint || this.$q.screen.height < breakpoint
          ? 'dialog'
          : 'menu'
      }
    },

    computed: {
      parsedBreakpoint: function parsedBreakpoint () {
        return parseInt(this.breakpoint, 10)
      }
    },

    watch: {
      '$q.screen.width': function $q_screen_width (width) {
        if (this.$refs.popup.showing !== true) {
          this.__updateType(width, this.$q.screen.height, this.parsedBreakpoint);
        }
      },

      '$q.screen.height': function $q_screen_height (height) {
        if (this.$refs.popup.showing !== true) {
          this.__updateType(this.$q.screen.width, height, this.parsedBreakpoint);
        }
      },

      breakpoint: function breakpoint (breakpoint$1) {
        if (this.$refs.popup.showing !== true) {
          this.__updateType(this.$q.screen.width, this.$q.screen.height, parseInt(breakpoint$1, 10));
        }
      }
    },

    methods: {
      toggle: function toggle (evt) {
        this.$refs.popup.toggle(evt);
      },

      show: function show (evt) {
        this.$refs.popup.show(evt);
      },

      hide: function hide (evt) {
        this.$refs.popup.hide(evt);
      },

      __onHide: function __onHide (evt) {
        this.__updateType(this.$q.screen.width, this.$q.screen.height, this.parsedBreakpoint);
        this.$emit('hide', evt);
      },

      __updateType: function __updateType (width, height, breakpoint) {
        var type = width < breakpoint || height < breakpoint
          ? 'dialog'
          : 'menu';

        if (this.type !== type) {
          this.type = type;
        }
      }
    },

    render: function render (h) {
      var def = slot(this, 'default');

      var props = (
        this.type === 'menu' &&
        def !== void 0 &&
        def[0] !== void 0 &&
        def[0].componentOptions !== void 0 &&
        def[0].componentOptions.Ctor !== void 0 &&
        def[0].componentOptions.Ctor.sealedOptions !== void 0 &&
        ['QDate', 'QTime', 'QCarousel', 'QColor'].includes(
          def[0].componentOptions.Ctor.sealedOptions.name
        )
      ) ? { cover: true, maxHeight: '99vh' } : {};

      var data = {
        ref: 'popup',
        props: Object.assign(props, this.$attrs),
        on: Object.assign({}, this.$listeners,
          {hide: this.__onHide})
      };

      var component;

      if (this.type === 'dialog') {
        component = QDialog;
      }
      else {
        component = QMenu;
        data.props.target = this.target;
        data.props.contextMenu = this.contextMenu;
        data.props.noParentEvent = true;
        data.props.separateClosePopup = true;
      }

      return h(component, data, def)
    }
  });

  function width$1 (val) {
    return { transform: ("scale3d(" + val + ",1,1)") }
  }

  var QLinearProgress = Vue.extend({
    name: 'QLinearProgress',

    mixins: [
      DarkMixin,
      getSizeMixin({
        xs: 2,
        sm: 4,
        md: 6,
        lg: 10,
        xl: 14
      })
    ],

    props: {
      value: {
        type: Number,
        default: 0
      },
      buffer: Number,

      color: String,
      trackColor: String,

      reverse: Boolean,
      stripe: Boolean,
      indeterminate: Boolean,
      query: Boolean,
      rounded: Boolean
    },

    computed: {
      motion: function motion () {
        return this.indeterminate === true || this.query === true
      },

      classes: function classes () {
        return 'q-linear-progress' +
          (this.color !== void 0 ? (" text-" + (this.color)) : '') +
          (this.reverse === true || this.query === true ? ' q-linear-progress--reverse' : '') +
          (this.rounded === true ? ' rounded-borders' : '')
      },

      trackStyle: function trackStyle () {
        return width$1(this.buffer !== void 0 ? this.buffer : 1)
      },

      trackClass: function trackClass () {
        return 'q-linear-progress__track--' + (this.isDark === true ? 'dark' : 'light') +
          (this.trackColor !== void 0 ? (" bg-" + (this.trackColor)) : '')
      },

      modelStyle: function modelStyle () {
        return width$1(this.motion ? 1 : this.value)
      },

      modelClasses: function modelClasses () {
        return ("q-linear-progress__model--" + (this.motion ? 'in' : '') + "determinate")
      },

      stripeStyle: function stripeStyle () {
        return { width: (this.value * 100) + '%' }
      },

      attrs: function attrs () {
        return {
          role: 'progressbar',
          'aria-valuemin': this.min,
          'aria-valuemax': this.max,
          'aria-valuenow': this.indeterminate === true ? void 0 : this.value
        }
      }
    },

    render: function render (h) {
      var child = [
        h('div', {
          staticClass: 'q-linear-progress__track absolute-full',
          style: this.trackStyle,
          class: this.trackClass
        }),

        h('div', {
          staticClass: 'q-linear-progress__model absolute-full',
          style: this.modelStyle,
          class: this.modelClasses
        })
      ];

      this.stripe === true && this.motion === false && child.push(
        h('div', {
          staticClass: 'q-linear-progress__stripe absolute-full',
          style: this.stripeStyle
        })
      );

      return h('div', {
        style: this.sizeStyle,
        class: this.classes,
        attrs: this.attrs,
        on: this.$listeners
      }, mergeSlot(child, this, 'default'))
    }
  });

  var
    PULLER_HEIGHT = 40,
    OFFSET_TOP = 20;

  var QPullToRefresh = Vue.extend({
    name: 'QPullToRefresh',

    directives: {
      TouchPan: TouchPan
    },

    props: {
      color: String,
      bgColor: String,
      icon: String,
      noMouse: Boolean,
      disable: Boolean,

      scrollTarget: {
        default: void 0
      }
    },

    data: function data () {
      return {
        state: 'pull',
        pullRatio: 0,
        pulling: false,
        pullPosition: -PULLER_HEIGHT,
        animating: false,
        positionCSS: {}
      }
    },

    computed: {
      style: function style () {
        return {
          opacity: this.pullRatio,
          transform: ("translateY(" + (this.pullPosition) + "px) rotate(" + (this.pullRatio * 360) + "deg)")
        }
      },

      classes: function classes () {
        return 'q-pull-to-refresh__puller row flex-center' +
          (this.animating === true ? ' q-pull-to-refresh__puller--animating' : '') +
          (this.bgColor !== void 0 ? (" bg-" + (this.bgColor)) : '')
      }
    },

    watch: {
      scrollTarget: function scrollTarget () {
        this.updateScrollTarget();
      }
    },

    methods: {
      trigger: function trigger () {
        var this$1 = this;

        this.$emit('refresh', function () {
          this$1.__animateTo({ pos: -PULLER_HEIGHT, ratio: 0 }, function () {
            this$1.state = 'pull';
          });
        });
      },

      updateScrollTarget: function updateScrollTarget () {
        this.scrollContainer = getScrollTarget(this.$el, this.scrollTarget);
      },

      __pull: function __pull (event) {
        if (event.isFinal === true) {
          if (this.pulling === true) {
            this.pulling = false;

            if (this.state === 'pulled') {
              this.state = 'refreshing';
              this.__animateTo({ pos: OFFSET_TOP });
              this.trigger();
            }
            else if (this.state === 'pull') {
              this.__animateTo({ pos: -PULLER_HEIGHT, ratio: 0 });
            }
          }

          return
        }

        if (this.animating === true || this.state === 'refreshing') {
          return false
        }

        if (event.isFirst === true) {
          if (getScrollPosition(this.scrollContainer) !== 0) {
            if (this.pulling) {
              this.pulling = false;
              this.state = 'pull';
              this.__animateTo({ pos: -PULLER_HEIGHT, ratio: 0 });
            }

            return false
          }

          this.pulling = true;

          var ref = this.$el.getBoundingClientRect();
          var top = ref.top;
          var left = ref.left;
          this.positionCSS = {
            top: top + 'px',
            left: left + 'px',
            width: window.getComputedStyle(this.$el).getPropertyValue('width')
          };
        }

        prevent(event.evt);

        var distance = Math.min(140, Math.max(0, event.distance.y));
        this.pullPosition = distance - PULLER_HEIGHT;
        this.pullRatio = between(distance / (OFFSET_TOP + PULLER_HEIGHT), 0, 1);

        var state = this.pullPosition > OFFSET_TOP ? 'pulled' : 'pull';
        if (this.state !== state) {
          this.state = state;
        }
      },

      __animateTo: function __animateTo (ref, done) {
        var this$1 = this;
        var pos = ref.pos;
        var ratio = ref.ratio;

        this.animating = true;
        this.pullPosition = pos;

        if (ratio !== void 0) {
          this.pullRatio = ratio;
        }

        clearTimeout(this.timer);
        this.timer = setTimeout(function () {
          this$1.animating = false;
          done && done();
        }, 300);
      }
    },

    mounted: function mounted () {
      this.updateScrollTarget();
    },

    beforeDestroy: function beforeDestroy () {
      clearTimeout(this.timer);
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-pull-to-refresh overflow-hidden',
        on: this.$listeners,
        directives: this.disable === true
          ? null
          : cache(this, 'dir#' + this.noMouse, [{
            name: 'touch-pan',
            modifiers: {
              down: true,
              mightPrevent: true,
              mouse: this.noMouse !== true
            },
            value: this.__pull
          }])
      }, [
        h('div', {
          staticClass: 'q-pull-to-refresh__content',
          class: this.pulling === true ? 'no-pointer-events' : ''
        }, slot(this, 'default')),

        h('div', {
          staticClass: 'q-pull-to-refresh__puller-container fixed row flex-center no-pointer-events z-top',
          style: this.positionCSS
        }, [
          h('div', {
            style: this.style,
            class: this.classes
          }, [
            this.state !== 'refreshing'
              ? h(QIcon, {
                props: {
                  name: this.icon || this.$q.iconSet.pullToRefresh.icon,
                  color: this.color,
                  size: '32px'
                }
              })
              : h(QSpinner, {
                props: {
                  size: '24px',
                  color: this.color
                }
              })
          ])
        ])
      ])
    }
  });

  var dragType = {
    MIN: 0,
    RANGE: 1,
    MAX: 2
  };

  var QRange = Vue.extend({
    name: 'QRange',

    mixins: [ SliderMixin ],

    props: {
      value: {
        type: Object,
        default: function () { return ({
          min: null,
          max: null
        }); },
        validator: function validator (val) {
          return 'min' in val && 'max' in val
        }
      },

      name: String,

      dragRange: Boolean,
      dragOnlyRange: Boolean,

      leftLabelColor: String,
      leftLabelTextColor: String,
      rightLabelColor: String,
      rightLabelTextColor: String,

      leftLabelValue: [String, Number],
      rightLabelValue: [String, Number]
    },

    data: function data () {
      return {
        model: {
          min: this.value.min === null ? this.min : this.value.min,
          max: this.value.max === null ? this.max : this.value.max
        },
        curMinRatio: 0,
        curMaxRatio: 0
      }
    },

    watch: {
      'value.min': function value_min (val) {
        this.model.min = val === null
          ? this.min
          : val;
      },

      'value.max': function value_max (val) {
        this.model.max = val === null
          ? this.max
          : val;
      },

      min: function min (value) {
        if (this.model.min < value) {
          this.model.min = value;
        }
        if (this.model.max < value) {
          this.model.max = value;
        }
      },

      max: function max (value) {
        if (this.model.min > value) {
          this.model.min = value;
        }
        if (this.model.max > value) {
          this.model.max = value;
        }
      }
    },

    computed: {
      ratioMin: function ratioMin () {
        return this.active === true ? this.curMinRatio : this.modelMinRatio
      },

      ratioMax: function ratioMax () {
        return this.active === true ? this.curMaxRatio : this.modelMaxRatio
      },

      modelMinRatio: function modelMinRatio () {
        return (this.model.min - this.min) / (this.max - this.min)
      },

      modelMaxRatio: function modelMaxRatio () {
        return (this.model.max - this.min) / (this.max - this.min)
      },

      trackStyle: function trackStyle () {
        var obj;

        return ( obj = {}, obj[this.horizProp] = 100 * this.ratioMin + '%', obj.width = 100 * (this.ratioMax - this.ratioMin) + '%', obj )
      },

      minThumbStyle: function minThumbStyle () {
        var obj;

        return ( obj = {}, obj[this.horizProp] = (100 * this.ratioMin) + '%', obj['z-index'] = this.__nextFocus === 'min' ? 2 : void 0, obj )
      },

      maxThumbStyle: function maxThumbStyle () {
        var obj;

        return ( obj = {}, obj[this.horizProp] = (100 * this.ratioMax) + '%', obj )
      },

      minThumbClass: function minThumbClass () {
        if (this.preventFocus === false && this.focus === 'min') {
          return 'q-slider--focus'
        }
      },

      maxThumbClass: function maxThumbClass () {
        if (this.preventFocus === false && this.focus === 'max') {
          return 'q-slider--focus'
        }
      },

      events: function events () {
        var this$1 = this;

        if (this.editable === true) {
          if (this.$q.platform.is.mobile === true) {
            return { click: this.__mobileClick }
          }

          var evt = { mousedown: this.__activate };

          this.dragOnlyRange === true && Object.assign(evt, {
            focus: function () { this$1.__focus('both'); },
            blur: this.__blur,
            keydown: this.__keydown,
            keyup: this.__keyup
          });

          return evt
        }
      },

      minEvents: function minEvents () {
        var this$1 = this;

        if (this.editable === true && this.$q.platform.is.mobile !== true && this.dragOnlyRange !== true) {
          return {
            focus: function () { this$1.__focus('min'); },
            blur: this.__blur,
            keydown: this.__keydown,
            keyup: this.__keyup
          }
        }
      },

      maxEvents: function maxEvents () {
        var this$1 = this;

        if (this.editable === true && this.$q.platform.is.mobile !== true && this.dragOnlyRange !== true) {
          return {
            focus: function () { this$1.__focus('max'); },
            blur: this.__blur,
            keydown: this.__keydown,
            keyup: this.__keyup
          }
        }
      },

      minPinClass: function minPinClass () {
        var color = this.leftLabelColor || this.labelColor;
        if (color) {
          return ("text-" + color)
        }
      },

      minPinTextClass: function minPinTextClass () {
        var color = this.leftLabelTextColor || this.labelTextColor;
        if (color) {
          return ("text-" + color)
        }
      },

      maxPinClass: function maxPinClass () {
        var color = this.rightLabelColor || this.labelColor;
        if (color) {
          return ("text-" + color)
        }
      },

      maxPinTextClass: function maxPinTextClass () {
        var color = this.rightLabelTextColor || this.labelTextColor;
        if (color) {
          return ("text-" + color)
        }
      },

      minLabel: function minLabel () {
        return this.leftLabelValue !== void 0
          ? this.leftLabelValue
          : this.model.min
      },

      maxLabel: function maxLabel () {
        return this.rightLabelValue !== void 0
          ? this.rightLabelValue
          : this.model.max
      },

      minPinStyle: function minPinStyle () {
        var percent = (this.reverse === true ? -this.ratioMin : this.ratioMin - 1);
        return this.__getPinStyle(percent, this.ratioMin)
      },

      maxPinStyle: function maxPinStyle () {
        var percent = (this.reverse === true ? -this.ratioMax : this.ratioMax - 1);
        return this.__getPinStyle(percent, this.ratioMax)
      },

      formAttrs: function formAttrs () {
        return {
          type: 'hidden',
          name: this.name,
          value: ((this.value.min) + "|" + (this.value.max))
        }
      }
    },

    methods: {
      __updateValue: function __updateValue (change) {
        if (this.model.min !== this.value.min || this.model.max !== this.value.max) {
          this.$emit('input', this.model);
        }
        change === true && this.$emit('change', this.model);
      },

      __getDragging: function __getDragging (event) {
        var ref = this.$el.getBoundingClientRect();
        var left = ref.left;
        var width = ref.width;
        var sensitivity = this.dragOnlyRange ? 0 : this.$refs.minThumb.offsetWidth / (2 * width),
          diff = this.max - this.min;

        var dragging = {
          left: left,
          width: width,
          valueMin: this.model.min,
          valueMax: this.model.max,
          ratioMin: (this.model.min - this.min) / diff,
          ratioMax: (this.model.max - this.min) / diff
        };

        var
          ratio = getRatio(event, dragging, this.isReversed),
          type;

        if (this.dragOnlyRange !== true && ratio < dragging.ratioMin + sensitivity) {
          type = dragType.MIN;
        }
        else if (this.dragOnlyRange === true || ratio < dragging.ratioMax - sensitivity) {
          if (this.dragRange || this.dragOnlyRange) {
            type = dragType.RANGE;
            Object.assign(dragging, {
              offsetRatio: ratio,
              offsetModel: getModel(ratio, this.min, this.max, this.step, this.decimals),
              rangeValue: dragging.valueMax - dragging.valueMin,
              rangeRatio: dragging.ratioMax - dragging.ratioMin
            });
          }
          else {
            type = dragging.ratioMax - ratio < ratio - dragging.ratioMin
              ? dragType.MAX
              : dragType.MIN;
          }
        }
        else {
          type = dragType.MAX;
        }

        dragging.type = type;
        this.__nextFocus = void 0;

        return dragging
      },

      __updatePosition: function __updatePosition (event, dragging) {
        if ( dragging === void 0 ) dragging = this.dragging;

        var
          ratio = getRatio(event, dragging, this.isReversed),
          model = getModel(ratio, this.min, this.max, this.step, this.decimals),
          pos;

        switch (dragging.type) {
          case dragType.MIN:
            if (ratio <= dragging.ratioMax) {
              pos = {
                minR: ratio,
                maxR: dragging.ratioMax,
                min: model,
                max: dragging.valueMax
              };
              this.__nextFocus = 'min';
            }
            else {
              pos = {
                minR: dragging.ratioMax,
                maxR: ratio,
                min: dragging.valueMax,
                max: model
              };
              this.__nextFocus = 'max';
            }
            break

          case dragType.MAX:
            if (ratio >= dragging.ratioMin) {
              pos = {
                minR: dragging.ratioMin,
                maxR: ratio,
                min: dragging.valueMin,
                max: model
              };
              this.__nextFocus = 'max';
            }
            else {
              pos = {
                minR: ratio,
                maxR: dragging.ratioMin,
                min: model,
                max: dragging.valueMin
              };
              this.__nextFocus = 'min';
            }
            break

          case dragType.RANGE:
            var
              ratioDelta = ratio - dragging.offsetRatio,
              minR = between(dragging.ratioMin + ratioDelta, 0, 1 - dragging.rangeRatio),
              modelDelta = model - dragging.offsetModel,
              min = between(dragging.valueMin + modelDelta, this.min, this.max - dragging.rangeValue);

            pos = {
              minR: minR,
              maxR: minR + dragging.rangeRatio,
              min: parseFloat(min.toFixed(this.decimals)),
              max: parseFloat((min + dragging.rangeValue).toFixed(this.decimals))
            };
            break
        }

        this.model = {
          min: pos.min,
          max: pos.max
        };

        // If either of the values to be emitted are null, set them to the defaults the user has entered.
        if (this.model.min === null || this.model.max === null) {
          this.model.min = pos.min || this.min;
          this.model.max = pos.max || this.max;
        }

        if (this.snap !== true || this.step === 0) {
          this.curMinRatio = pos.minR;
          this.curMaxRatio = pos.maxR;
        }
        else {
          var diff = this.max - this.min;
          this.curMinRatio = (this.model.min - this.min) / diff;
          this.curMaxRatio = (this.model.max - this.min) / diff;
        }
      },

      __focus: function __focus (which) {
        this.focus = which;
      },

      __keydown: function __keydown (evt) {
        var obj;

        if (!keyCodes.includes(evt.keyCode)) {
          return
        }

        stopAndPrevent(evt);

        var
          step = ([34, 33].includes(evt.keyCode) ? 10 : 1) * this.computedStep,
          offset = [34, 37, 40].includes(evt.keyCode) ? -step : step;

        if (this.dragOnlyRange) {
          var interval = this.dragOnlyRange ? this.model.max - this.model.min : 0;

          var min = between(
            parseFloat((this.model.min + offset).toFixed(this.decimals)),
            this.min,
            this.max - interval
          );

          this.model = {
            min: min,
            max: parseFloat((min + interval).toFixed(this.decimals))
          };
        }
        else if (this.focus === false) {
          return
        }
        else {
          var which = this.focus;

          this.model = Object.assign({}, this.model,
            ( obj = {}, obj[which] = between(
              parseFloat((this.model[which] + offset).toFixed(this.decimals)),
              which === 'min' ? this.min : this.model.min,
              which === 'max' ? this.max : this.model.max
            ), obj ));
        }

        this.__updateValue();
      },

      __getThumb: function __getThumb (h, which) {
        var child = [
          this.__getThumbSvg(h),
          h('div', { staticClass: 'q-slider__focus-ring' })
        ];

        if (this.label === true || this.labelAlways === true) {
          child.push(
            h('div', {
              staticClass: 'q-slider__pin absolute',
              style: this[which + 'PinStyle'].pin,
              class: this[which + 'PinClass']
            }, [
              h('div', { staticClass: 'q-slider__pin-text-container', style: this[which + 'PinStyle'].pinTextContainer }, [
                h('span', {
                  staticClass: 'q-slider__pin-text',
                  class: this[which + 'PinTextClass']
                }, [
                  this[which + 'Label']
                ])
              ])
            ]),

            h('div', {
              staticClass: 'q-slider__arrow',
              class: this[which + 'PinClass']
            })
          );
        }

        return h('div', {
          ref: which + 'Thumb',
          staticClass: 'q-slider__thumb-container absolute non-selectable',
          style: this[which + 'ThumbStyle'],
          class: this[which + 'ThumbClass'],
          on: this[which + 'Events'],
          attrs: { tabindex: this.dragOnlyRange !== true ? this.computedTabindex : null }
        }, child)
      }
    },

    render: function render (h) {
      var track = [
        h('div', {
          staticClass: 'q-slider__track absolute',
          style: this.trackStyle
        })
      ];

      this.markers === true && track.push(
        h('div', {
          staticClass: 'q-slider__track-markers absolute-full fit',
          style: this.markerStyle
        })
      );

      var child = [
        h('div', {
          staticClass: 'q-slider__track-container absolute'
        }, track),

        this.__getThumb(h, 'min'),
        this.__getThumb(h, 'max')
      ];

      if (this.name !== void 0 && this.disable !== true) {
        this.__injectFormInput(child, 'push');
      }

      return h('div', {
        staticClass: this.value.min === null || this.value.max === null
          ? 'q-slider--no-value'
          : void 0,
        attrs: Object.assign({}, this.attrs,
          {'aria-valuenow': this.value.min + '|' + this.value.max,
          tabindex: this.dragOnlyRange && !this.$q.platform.is.mobile
            ? this.computedTabindex
            : null}),
        class: this.classes,
        on: this.events,
        directives: this.editable === true ? cache(this, 'dir', [{
          name: 'touch-pan',
          value: this.__pan,
          modifiers: {
            horizontal: true,
            prevent: true,
            stop: true,
            mouse: true,
            mouseAllDir: true
          }
        }]) : null
      }, child)
    }
  });

  var QRating = Vue.extend({
    name: 'QRating',

    mixins: [ SizeMixin, FormMixin ],

    props: {
      value: {
        type: Number,
        required: true
      },

      max: {
        type: [String, Number],
        default: 5
      },

      icon: [String, Array],
      iconHalf: [String, Array],
      iconSelected: [String, Array],

      color: [String, Array],
      colorHalf: [String, Array],
      colorSelected: [String, Array],

      noReset: Boolean,
      noDimming: Boolean,

      readonly: Boolean,
      disable: Boolean
    },

    data: function data () {
      return {
        mouseModel: 0
      }
    },

    computed: {
      editable: function editable () {
        return this.readonly !== true && this.disable !== true
      },

      classes: function classes () {
        return "q-rating--" + (this.editable === true ? '' : 'non-') + "editable" +
          (this.noDimming === true ? ' q-rating--no-dimming' : '') +
          (this.disable === true ? ' disabled' : '') +
          (this.color !== void 0 && Array.isArray(this.color) === false ? (" text-" + (this.color)) : '')
      },

      iconData: function iconData () {
        var
          iconLen = Array.isArray(this.icon) === true ? this.icon.length : 0,
          selIconLen = Array.isArray(this.iconSelected) === true ? this.iconSelected.length : 0,
          halfIconLen = Array.isArray(this.iconHalf) === true ? this.iconHalf.length : 0,
          colorLen = Array.isArray(this.color) === true ? this.color.length : 0,
          selColorLen = Array.isArray(this.colorSelected) === true ? this.colorSelected.length : 0,
          halfColorLen = Array.isArray(this.colorHalf) === true ? this.colorHalf.length : 0;

        return {
          iconLen: iconLen,
          icon: iconLen > 0 ? this.icon[iconLen - 1] : this.icon,
          selIconLen: selIconLen,
          selIcon: selIconLen > 0 ? this.iconSelected[selIconLen - 1] : this.iconSelected,
          halfIconLen: halfIconLen,
          halfIcon: halfIconLen > 0 ? this.iconHalf[selIconLen - 1] : this.iconHalf,
          colorLen: colorLen,
          color: colorLen > 0 ? this.color[colorLen - 1] : this.color,
          selColorLen: selColorLen,
          selColor: selColorLen > 0 ? this.colorSelected[selColorLen - 1] : this.colorSelected,
          halfColorLen: halfColorLen,
          halfColor: halfColorLen > 0 ? this.colorHalf[halfColorLen - 1] : this.colorHalf
        }
      },

      attrs: function attrs () {
        if (this.disable === true) {
          return { 'aria-disabled': '' }
        }
        if (this.readonly === true) {
          return { 'aria-readonly': '' }
        }
      }
    },

    methods: {
      __set: function __set (value) {
        if (this.editable === true) {
          var
            model = between(parseInt(value, 10), 1, parseInt(this.max, 10)),
            newVal = this.noReset !== true && this.value === model ? 0 : model;

          newVal !== this.value && this.$emit('input', newVal);
          this.mouseModel = 0;
        }
      },

      __setHoverValue: function __setHoverValue (value) {
        if (this.editable === true) {
          this.mouseModel = value;
        }
      },

      __keyup: function __keyup (e, i) {
        switch (e.keyCode) {
          case 13:
          case 32:
            this.__set(i);
            return stopAndPrevent(e)
          case 37: // LEFT ARROW
          case 40: // DOWN ARROW
            if (this.$refs[("rt" + (i - 1))]) {
              this.$refs[("rt" + (i - 1))].focus();
            }
            return stopAndPrevent(e)
          case 39: // RIGHT ARROW
          case 38: // UP ARROW
            if (this.$refs[("rt" + (i + 1))]) {
              this.$refs[("rt" + (i + 1))].focus();
            }
            return stopAndPrevent(e)
        }
      }
    },

    render: function render (h) {
      var this$1 = this;
      var obj;

      var
        child = [],
        tabindex = this.editable === true ? 0 : null,
        icons = this.iconData,
        ceil = Math.ceil(this.value);

      var halfIndex = this.iconHalf === void 0 || ceil === this.value
        ? -1
        : ceil;

      var loop = function ( i ) {
        var
          active = (this$1.mouseModel === 0 && this$1.value >= i) || (this$1.mouseModel > 0 && this$1.mouseModel >= i),
          half = halfIndex === i && this$1.mouseModel < i,
          exSelected = this$1.mouseModel > 0 && (half === true ? ceil : this$1.value) >= i && this$1.mouseModel < i,
          name = half === true
            ? (i <= icons.halfIconLen ? this$1.iconHalf[i - 1] : icons.halfIcon)
            : (
              icons.selIcon !== void 0 && (active === true || exSelected === true)
                ? (i <= icons.selIconLen ? this$1.iconSelected[i - 1] : icons.selIcon)
                : (i <= icons.iconLen ? this$1.icon[i - 1] : icons.icon)
            ),
          color = half === true
            ? (i <= icons.halfColorLen ? this$1.colorHalf[i - 1] : icons.halfColor)
            : (
              icons.selColor !== void 0 && active === true
                ? (i <= icons.selColorLen ? this$1.colorSelected[i - 1] : icons.selColor)
                : (i <= icons.colorLen ? this$1.color[i - 1] : icons.color)
            );

        child.push(
          h(QIcon, {
            key: i,
            ref: ("rt" + i),
            staticClass: 'q-rating__icon',
            class: ( obj = {
              'q-rating__icon--active': active === true || half === true,
              'q-rating__icon--exselected': exSelected,
              'q-rating__icon--hovered': this$1.mouseModel === i
            }, obj[("text-" + color)] = color !== void 0, obj ),
            props: { name: name || this$1.$q.iconSet.rating.icon },
            attrs: { tabindex: tabindex },
            on: cache(this$1, 'i#' + i, {
              click: function () { this$1.__set(i); },
              mouseover: function () { this$1.__setHoverValue(i); },
              mouseout: function () { this$1.mouseModel = 0; },
              focus: function () { this$1.__setHoverValue(i); },
              blur: function () { this$1.mouseModel = 0; },
              keyup: function (e) { this$1.__keyup(e, i); }
            })
          }, slot(this$1, ("tip-" + i)))
        );
      };

      for (var i = 1; i <= this$1.max; i++) loop( i );

      if (this.name !== void 0 && this.disable !== true) {
        this.__injectFormInput(child, 'push');
      }

      return h('div', {
        staticClass: 'q-rating row inline items-center',
        class: this.classes,
        style: this.sizeStyle,
        attrs: this.attrs,
        on: this.$listeners
      }, child)
    }
  });

  var QResponsive = Vue.extend({
    name: 'QResponsive',

    mixins: [ RatioMixin ],

    render: function render (h) {
      return h('div', {
        staticClass: 'q-responsive',
        on: this.$listeners
      }, [
        h('div', {
          staticClass: 'q-responsive__filler overflow-hidden'
        }, [
          h('div', { style: this.ratioStyle })
        ]),

        h('div', {
          staticClass: 'q-responsive__content absolute-full fit'
        }, slot(this, 'default'))
      ])
    }
  });

  var QScrollArea = Vue.extend({
    name: 'QScrollArea',

    mixins: [ DarkMixin ],

    directives: {
      TouchPan: TouchPan
    },

    props: {
      barStyle: [ Array, String, Object ],
      thumbStyle: Object,
      contentStyle: [ Array, String, Object ],
      contentActiveStyle: [ Array, String, Object ],

      delay: {
        type: [String, Number],
        default: 1000
      },

      visible: {
        type: Boolean,
        default: null
      },

      horizontal: Boolean
    },

    data: function data () {
      return {
        // state management
        tempShowing: false,
        panning: false,
        hover: false,

        // other...
        containerWidth: 0,
        containerHeight: 0,
        scrollPosition: 0,
        scrollSize: 0
      }
    },

    computed: {
      classes: function classes () {
        return 'q-scrollarea' +
          (this.isDark === true ? ' q-scrollarea--dark' : '')
      },

      thumbHidden: function thumbHidden () {
        return (
          (this.visible === null ? this.hover : this.visible) !== true &&
          this.tempShowing === false &&
          this.panning === false
        ) || this.scrollSize <= this.containerSize
      },

      thumbSize: function thumbSize () {
        return Math.round(
          between(
            this.containerSize * this.containerSize / this.scrollSize,
            50,
            this.containerSize
          )
        )
      },

      style: function style () {
        var pos = this.scrollPercentage * (this.containerSize - this.thumbSize);
        return Object.assign(
          {},
          this.thumbStyle,
          this.horizontal === true
            ? {
              left: (pos + "px"),
              width: ((this.thumbSize) + "px")
            }
            : {
              top: (pos + "px"),
              height: ((this.thumbSize) + "px")
            }
        )
      },

      mainStyle: function mainStyle () {
        return this.thumbHidden === true
          ? this.contentStyle
          : this.contentActiveStyle
      },

      scrollPercentage: function scrollPercentage () {
        var p = between(this.scrollPosition / (this.scrollSize - this.containerSize), 0, 1);
        return Math.round(p * 10000) / 10000
      },

      containerSize: function containerSize () {
        return this[("container" + (this.dirProps.suffix))]
      },

      dirProps: function dirProps () {
        return this.horizontal === true
          ? { prefix: 'horizontal', suffix: 'Width', scroll: 'scrollLeft', classSuffix: 'h absolute-bottom', dir: 'right', dist: 'x' }
          : { prefix: 'vertical', suffix: 'Height', scroll: 'scrollTop', classSuffix: 'v absolute-right', dir: 'down', dist: 'y' }
      },

      thumbClass: function thumbClass () {
        return "q-scrollarea__thumb--" + (this.dirProps.classSuffix) +
          (this.thumbHidden === true ? ' q-scrollarea__thumb--invisible' : '')
      },

      barClass: function barClass () {
        return "q-scrollarea__bar--" + (this.dirProps.classSuffix) +
          (this.thumbHidden === true ? ' q-scrollarea__bar--invisible' : '')
      }
    },

    methods: {
      getScrollTarget: function getScrollTarget () {
        return this.$refs.target
      },

      getScrollPosition: function getScrollPosition () {
        return this.scrollPosition
      },

      setScrollPosition: function setScrollPosition$1 (offset, duration) {
        var fn = this.horizontal === true
          ? setHorizontalScrollPosition
          : setScrollPosition;

        fn(this.$refs.target, offset, duration);
      },

      __updateContainer: function __updateContainer (ref) {
        var height = ref.height;
        var width = ref.width;

        var change = false;

        if (this.containerWidth !== width) {
          this.containerWidth = width;
          change = true;
        }

        if (this.containerHeight !== height) {
          this.containerHeight = height;
          change = true;
        }

        change === true && this.__startTimer();
      },

      __updateScroll: function __updateScroll (info) {
        if (this.scrollPosition !== info.position) {
          this.scrollPosition = info.position;
          this.__startTimer();
        }
      },

      __updateScrollSize: function __updateScrollSize (ref) {
        var height = ref.height;
        var width = ref.width;

        if (this.horizontal === true) {
          if (this.scrollSize !== width) {
            this.scrollSize = width;
            this.__startTimer();
          }
        }
        else if (this.scrollSize !== height) {
          this.scrollSize = height;
          this.__startTimer();
        }
      },

      __panThumb: function __panThumb (e) {
        if (e.isFirst === true) {
          if (this.thumbHidden === true) {
            return
          }

          this.refPos = this.scrollPosition;
          this.panning = true;
        }
        else if (this.panning !== true) {
          return
        }

        if (e.isFinal === true) {
          this.panning = false;
        }

        var multiplier = (this.scrollSize - this.containerSize) / (this.containerSize - this.thumbSize);
        var distance = e.distance[this.dirProps.dist];
        var pos = this.refPos + (e.direction === this.dirProps.dir ? 1 : -1) * distance * multiplier;

        this.__setScroll(pos);
      },

      __mouseDown: function __mouseDown (evt) {
        if (this.thumbHidden !== true) {
          var pos = evt[("offset" + (this.horizontal === true ? 'X' : 'Y'))] - this.thumbSize / 2;
          this.__setScroll(pos / this.containerSize * this.scrollSize);

          // activate thumb pan
          if (this.$refs.thumb !== void 0) {
            this.$refs.thumb.dispatchEvent(new MouseEvent(evt.type, evt));
          }
        }
      },

      __startTimer: function __startTimer () {
        var this$1 = this;

        if (this.tempShowing === true) {
          clearTimeout(this.timer);
        }
        else {
          this.tempShowing = true;
        }

        this.timer = setTimeout(function () {
          this$1.tempShowing = false;
        }, this.delay);

        this.__emitScroll();
      },

      __setScroll: function __setScroll (offset) {
        this.$refs.target[this.dirProps.scroll] = offset;
      }
    },

    render: function render (h) {
      var this$1 = this;

      return h('div', {
        class: this.classes,
        on: cache(this, 'desk', {
          mouseenter: function () { this$1.hover = true; },
          mouseleave: function () { this$1.hover = false; }
        })
      }, [
        h('div', {
          ref: 'target',
          staticClass: 'scroll relative-position fit hide-scrollbar'
        }, [
          h('div', {
            staticClass: 'absolute',
            style: this.mainStyle,
            class: ("full-" + (this.horizontal === true ? 'height' : 'width'))
          }, mergeSlot([
            h(QResizeObserver, {
              on: cache(this, 'resizeIn', { resize: this.__updateScrollSize })
            })
          ], this, 'default')),

          h(QScrollObserver, {
            props: { horizontal: this.horizontal },
            on: cache(this, 'scroll', { scroll: this.__updateScroll })
          })
        ]),

        h(QResizeObserver, {
          on: cache(this, 'resizeOut', { resize: this.__updateContainer })
        }),

        h('div', {
          staticClass: 'q-scrollarea__bar',
          style: this.barStyle,
          class: this.barClass,
          on: cache(this, 'bar', {
            mousedown: this.__mouseDown
          })
        }),

        h('div', {
          ref: 'thumb',
          staticClass: 'q-scrollarea__thumb',
          style: this.style,
          class: this.thumbClass,
          directives: cache(this, 'thumb#' + this.horizontal, [{
            name: 'touch-pan',
            modifiers: {
              vertical: this.horizontal !== true,
              horizontal: this.horizontal,
              prevent: true,
              mouse: true,
              mouseAllDir: true
            },
            value: this.__panThumb
          }])
        })
      ])
    },

    created: function created () {
      var this$1 = this;

      // we have lots of listeners, so
      // ensure we're not emitting same info
      // multiple times
      this.__emitScroll = debounce(function () {
        if (this$1.$listeners.scroll !== void 0) {
          var info = { ref: this$1 };
          var prefix = this$1.dirProps.prefix;

          info[prefix + 'Position'] = this$1.scrollPosition;
          info[prefix + 'Percentage'] = this$1.scrollPercentage;
          info[prefix + 'Size'] = this$1.scrollSize;
          info[prefix + 'ContainerSize'] = this$1.containerSize;

          this$1.$emit('scroll', info);
        }
      }, 0);
    }
  });

  var aggBucketSize = 1000;

  var slice = Array.prototype.slice;

  function sumFn (acc, h) {
    return acc + h
  }

  function getScrollDetails (
    parent,
    child,
    beforeRef,
    afterRef,
    horizontal,
    stickyStart,
    stickyEnd
  ) {
    var
      parentCalc = parent === window ? document.scrollingElement || document.documentElement : parent,
      propElSize = horizontal === true ? 'offsetWidth' : 'offsetHeight',
      details = {
        scrollStart: 0,
        scrollViewSize: -stickyStart - stickyEnd,
        scrollMaxSize: 0,
        offsetStart: -stickyStart,
        offsetEnd: -stickyEnd
      };

    if (horizontal === true) {
      if (parent === window) {
        details.scrollStart = window.pageXOffset || window.scrollX || document.body.scrollLeft || 0;
        details.scrollViewSize += window.innerWidth;
      }
      else {
        details.scrollStart = parentCalc.scrollLeft;
        details.scrollViewSize += parentCalc.clientWidth;
      }
      details.scrollMaxSize = parentCalc.scrollWidth;
    }
    else {
      if (parent === window) {
        details.scrollStart = window.pageYOffset || window.scrollY || document.body.scrollTop || 0;
        details.scrollViewSize += window.innerHeight;
      }
      else {
        details.scrollStart = parentCalc.scrollTop;
        details.scrollViewSize += parentCalc.clientHeight;
      }
      details.scrollMaxSize = parentCalc.scrollHeight;
    }

    if (beforeRef !== void 0) {
      for (var el = beforeRef.previousElementSibling; el !== null; el = el.previousElementSibling) {
        details.offsetStart += el[propElSize];
      }
    }
    if (afterRef !== void 0) {
      for (var el$1 = afterRef.nextElementSibling; el$1 !== null; el$1 = el$1.nextElementSibling) {
        details.offsetEnd += el$1[propElSize];
      }
    }

    if (child !== parent) {
      var
        parentRect = parentCalc.getBoundingClientRect(),
        childRect = child.getBoundingClientRect();

      if (horizontal === true) {
        details.offsetStart += childRect.left - parentRect.left;
        details.offsetEnd -= childRect.width;
      }
      else {
        details.offsetStart += childRect.top - parentRect.top;
        details.offsetEnd -= childRect.height;
      }

      if (parent !== window) {
        details.offsetStart += details.scrollStart;
      }
      details.offsetEnd += details.scrollMaxSize - details.offsetStart;
    }

    return details
  }

  function setScroll$1 (parent, scroll, horizontal) {
    if (parent === window) {
      if (horizontal === true) {
        window.scrollTo(scroll, window.pageYOffset || window.scrollY || document.body.scrollTop || 0);
      }
      else {
        window.scrollTo(window.pageXOffset || window.scrollX || document.body.scrollLeft || 0, scroll);
      }
    }
    else {
      parent[horizontal === true ? 'scrollLeft' : 'scrollTop'] = scroll;
    }
  }

  function sumSize (sizeAgg, size, from, to) {
    if (from >= to) { return 0 }

    var
      lastTo = size.length,
      fromAgg = Math.floor(from / aggBucketSize),
      toAgg = Math.floor((to - 1) / aggBucketSize) + 1;

    var total = sizeAgg.slice(fromAgg, toAgg).reduce(sumFn, 0);

    if (from % aggBucketSize !== 0) {
      total -= size.slice(fromAgg * aggBucketSize, from).reduce(sumFn, 0);
    }
    if (to % aggBucketSize !== 0 && to !== lastTo) {
      total -= size.slice(to, toAgg * aggBucketSize).reduce(sumFn, 0);
    }

    return total
  }

  var commonVirtScrollProps = {
    virtualScrollSliceSize: {
      type: Number,
      default: 30
    },

    virtualScrollItemSize: {
      type: Number,
      default: 24
    },

    virtualScrollStickySizeStart: {
      type: Number,
      default: 0
    },

    virtualScrollStickySizeEnd: {
      type: Number,
      default: 0
    }
  };

  var commonVirtPropsList = Object.keys(commonVirtScrollProps);

  var VirtualScroll = {
    props: Object.assign({}, {virtualScrollHorizontal: Boolean},
      commonVirtScrollProps),

    data: function data () {
      return {
        virtualScrollSliceRange: { from: 0, to: 0 }
      }
    },

    watch: {
      virtualScrollHorizontal: function virtualScrollHorizontal () {
        this.__setVirtualScrollSize();
      },

      needsReset: function needsReset () {
        this.reset();
      }
    },

    computed: {
      needsReset: function needsReset () {
        var this$1 = this;

        return ['virtualScrollItemSize', 'virtualScrollHorizontal']
          .map(function (p) { return this$1[p]; }).join(';')
      }
    },

    methods: {
      reset: function reset () {
        this.__resetVirtualScroll(this.prevToIndex, true);
      },

      refresh: function refresh (toIndex) {
        this.__resetVirtualScroll(toIndex === void 0 ? this.prevToIndex : toIndex);
      },

      scrollTo: function scrollTo (toIndex) {
        var scrollEl = this.__getVirtualScrollTarget();

        if (scrollEl === void 0 || scrollEl === null || scrollEl.nodeType === 8) {
          return
        }

        this.__setVirtualScrollSliceRange(
          scrollEl,
          getScrollDetails(
            scrollEl,
            this.__getVirtualScrollEl(),
            this.$refs.before,
            this.$refs.after,
            this.virtualScrollHorizontal,
            this.virtualScrollStickySizeStart,
            this.virtualScrollStickySizeEnd
          ),
          Math.min(this.virtualScrollLength - 1, Math.max(0, parseInt(toIndex, 10) || 0)),
          0,
          this.prevToIndex > -1 && toIndex > this.prevToIndex ? 'end' : 'start'
        );
      },

      __onVirtualScrollEvt: function __onVirtualScrollEvt () {
        var scrollEl = this.__getVirtualScrollTarget();

        if (scrollEl === void 0 || scrollEl === null || scrollEl.nodeType === 8) {
          return
        }

        var
          scrollDetails = getScrollDetails(
            scrollEl,
            this.__getVirtualScrollEl(),
            this.$refs.before,
            this.$refs.after,
            this.virtualScrollHorizontal,
            this.virtualScrollStickySizeStart,
            this.virtualScrollStickySizeEnd
          ),
          scrollMaxStart = scrollDetails.scrollMaxSize - Math.max(scrollDetails.scrollViewSize, scrollDetails.offsetEnd),
          listLastIndex = this.virtualScrollLength - 1;

        if (this.prevScrollStart === scrollDetails.scrollStart) {
          return
        }
        this.prevScrollStart = void 0;

        this.__updateVirtualScrollSizes(this.virtualScrollSliceRange.from);

        if (scrollMaxStart > 0 && scrollDetails.scrollStart >= scrollMaxStart) {
          this.__setVirtualScrollSliceRange(
            scrollEl,
            scrollDetails,
            this.virtualScrollLength - 1,
            scrollDetails.scrollMaxSize - scrollDetails.offsetEnd - this.virtualScrollSizesAgg.reduce(sumFn, 0)
          );

          return
        }

        var
          toIndex = 0,
          listOffset = scrollDetails.scrollStart - scrollDetails.offsetStart,
          offset = listOffset;

        for (var j = 0; listOffset >= this.virtualScrollSizesAgg[j] && toIndex < listLastIndex; j++) {
          listOffset -= this.virtualScrollSizesAgg[j];
          toIndex += aggBucketSize;
        }

        while (listOffset > 0 && toIndex < listLastIndex) {
          listOffset -= this.virtualScrollSizes[toIndex];
          if (listOffset > -scrollDetails.scrollViewSize) {
            toIndex++;
            offset = listOffset;
          }
          else {
            offset = this.virtualScrollSizes[toIndex] + listOffset;
          }
        }

        this.__setVirtualScrollSliceRange(
          scrollEl,
          scrollDetails,
          toIndex,
          offset
        );
      },

      __setVirtualScrollSliceRange: function __setVirtualScrollSliceRange (scrollEl, scrollDetails, toIndex, offset, align) {
        var this$1 = this;

        var
          from = Math.max(0, Math.ceil(toIndex - (align === void 0 ? 3 : 2) * this.virtualScrollSliceSizeComputed / 6)),
          to = from + this.virtualScrollSliceSizeComputed;

        if (to > this.virtualScrollLength) {
          to = this.virtualScrollLength;
          from = Math.max(0, to - this.virtualScrollSliceSizeComputed);
        }

        var rangeChanged = from !== this.virtualScrollSliceRange.from || to !== this.virtualScrollSliceRange.to;

        if (rangeChanged === false && align === void 0) {
          this.__emitScroll(toIndex);

          return
        }

        if (rangeChanged === true) {
          this.virtualScrollSliceRange = { from: from, to: to };
          this.virtualScrollPaddingBefore = sumSize(this.virtualScrollSizesAgg, this.virtualScrollSizes, 0, from);
          this.virtualScrollPaddingAfter = sumSize(this.virtualScrollSizesAgg, this.virtualScrollSizes, to, this.virtualScrollLength);
        }

        this.$nextTick(function () {
          if (rangeChanged === true) {
            this$1.__updateVirtualScrollSizes(from);
          }

          var
            posStart = this$1.virtualScrollSizes.slice(from, toIndex).reduce(sumFn, scrollDetails.offsetStart + this$1.virtualScrollPaddingBefore),
            posEnd = posStart + this$1.virtualScrollSizes[toIndex];

          var scrollPosition = posStart + offset;

          if (align !== void 0) {
            scrollPosition = scrollDetails.scrollStart < posStart && posEnd < scrollDetails.scrollStart + scrollDetails.scrollViewSize
              ? scrollDetails.scrollStart
              : (align === 'end' ? posEnd - scrollDetails.scrollViewSize : posStart);
          }

          this$1.prevScrollStart = scrollPosition;

          this$1.__setScroll(
            scrollEl,
            scrollPosition,
            this$1.virtualScrollHorizontal
          );

          this$1.__emitScroll(toIndex);
        });
      },

      __updateVirtualScrollSizes: function __updateVirtualScrollSizes (from) {
        var contentEl = this.$refs.content;

        if (contentEl !== void 0) {
          var
            children = slice.call(contentEl.children).filter(function (el) { return el.classList.contains('q-virtual-scroll--skip') === false; }),
            childrenLength = children.length,
            sizeProp = this.virtualScrollHorizontal === true ? 'offsetWidth' : 'offsetHeight';

          var
            index = from,
            size, diff;

          for (var i = 0; i < childrenLength;) {
            size = children[i][sizeProp];
            i++;

            while (i < childrenLength && children[i].classList.contains('q-virtual-scroll--with-prev') === true) {
              size += children[i][sizeProp];
              i++;
            }

            diff = size - this.virtualScrollSizes[index];

            if (diff !== 0) {
              this.virtualScrollSizes[index] += diff;
              this.virtualScrollSizesAgg[Math.floor(index / aggBucketSize)] += diff;
            }

            index++;
          }
        }
      },

      __resetVirtualScroll: function __resetVirtualScroll (toIndex, fullReset) {
        var this$1 = this;

        var defaultSize = this.virtualScrollItemSize;

        if (fullReset === true || Array.isArray(this.virtualScrollSizes) === false) {
          this.virtualScrollSizes = [];
        }

        var oldVirtualScrollSizesLength = this.virtualScrollSizes.length;

        this.virtualScrollSizes.length = this.virtualScrollLength;

        for (var i = this.virtualScrollLength - 1; i >= oldVirtualScrollSizesLength; i--) {
          this.virtualScrollSizes[i] = defaultSize;
        }

        var jMax = Math.floor((this.virtualScrollLength - 1) / aggBucketSize);
        this.virtualScrollSizesAgg = [];
        for (var j = 0; j <= jMax; j++) {
          var size = 0;
          var iMax = Math.min((j + 1) * aggBucketSize, this.virtualScrollLength);
          for (var i$1 = j * aggBucketSize; i$1 < iMax; i$1++) {
            size += this.virtualScrollSizes[i$1];
          }
          this.virtualScrollSizesAgg.push(size);
        }

        this.prevToIndex = -1;
        this.prevScrollStart = void 0;

        if (toIndex >= 0) {
          this.__updateVirtualScrollSizes(this.virtualScrollSliceRange.from);

          this.$nextTick(function () {
            this$1.scrollTo(toIndex);
          });
        }
        else {
          this.virtualScrollPaddingBefore = sumSize(this.virtualScrollSizesAgg, this.virtualScrollSizes, 0, this.virtualScrollSliceRange.from);
          this.virtualScrollPaddingAfter = sumSize(this.virtualScrollSizesAgg, this.virtualScrollSizes, this.virtualScrollSliceRange.to, this.virtualScrollLength);

          this.__onVirtualScrollEvt();
        }
      },

      __setVirtualScrollSize: function __setVirtualScrollSize () {
        if (this.virtualScrollHorizontal === true) {
          this.virtualScrollSliceSizeComputed = typeof window === 'undefined'
            ? this.virtualScrollSliceSize
            : Math.max(this.virtualScrollSliceSize, Math.ceil(window.innerWidth / this.virtualScrollItemSize * 2));
        }
        else {
          this.virtualScrollSliceSizeComputed = typeof window === 'undefined'
            ? this.virtualScrollSliceSize
            : Math.max(this.virtualScrollSliceSize, Math.ceil(window.innerHeight / this.virtualScrollItemSize * 2));
        }
      },

      __padVirtualScroll: function __padVirtualScroll (h, tag, content) {
        var obj, obj$1, obj$2, obj$3;

        var paddingSize = this.virtualScrollHorizontal === true ? 'width' : 'height';

        return [
          tag === 'tbody'
            ? h(tag, {
              staticClass: 'q-virtual-scroll__padding',
              key: 'before',
              ref: 'before'
            }, [
              h('tr', [
                h('td', {
                  style: ( obj = {}, obj[paddingSize] = ((this.virtualScrollPaddingBefore) + "px"), obj ),
                  attrs: { colspan: '100%' }
                })
              ])
            ])
            : h(tag, {
              staticClass: 'q-virtual-scroll__padding',
              key: 'before',
              ref: 'before',
              style: ( obj$1 = {}, obj$1[paddingSize] = ((this.virtualScrollPaddingBefore) + "px"), obj$1 )
            }),

          h(tag, {
            staticClass: 'q-virtual-scroll__content',
            key: 'content',
            ref: 'content'
          }, content),

          tag === 'tbody'
            ? h(tag, {
              staticClass: 'q-virtual-scroll__padding',
              key: 'after',
              ref: 'after'
            }, [
              h('tr', [
                h('td', {
                  style: ( obj$2 = {}, obj$2[paddingSize] = ((this.virtualScrollPaddingAfter) + "px"), obj$2 ),
                  attrs: { colspan: '100%' }
                })
              ])
            ])
            : h(tag, {
              staticClass: 'q-virtual-scroll__padding',
              key: 'after',
              ref: 'after',
              style: ( obj$3 = {}, obj$3[paddingSize] = ((this.virtualScrollPaddingAfter) + "px"), obj$3 )
            })
        ]
      },

      __emitScroll: function __emitScroll (index) {
        if (this.prevToIndex !== index) {
          this.$listeners['virtual-scroll'] !== void 0 && this.$emit('virtual-scroll', {
            index: index,
            from: this.virtualScrollSliceRange.from,
            to: this.virtualScrollSliceRange.to - 1,
            direction: index < this.prevToIndex ? 'decrease' : 'increase',
            ref: this
          });

          this.prevToIndex = index;
        }
      }
    },

    created: function created () {
      this.__setVirtualScrollSize();
    },

    beforeMount: function beforeMount () {
      this.__onVirtualScrollEvt = debounce(this.__onVirtualScrollEvt, 70);
      this.__setScroll = frameDebounce(setScroll$1);
      this.__setVirtualScrollSize();
    }
  };

  var validateNewValueMode = function (v) { return ['add', 'add-unique', 'toggle'].includes(v); };

  var QSelect = Vue.extend({
    name: 'QSelect',

    mixins: [ QField, VirtualScroll, CompositionMixin, FormFieldMixin ],

    props: {
      value: {
        required: true
      },

      multiple: Boolean,

      displayValue: [String, Number],
      displayValueSanitize: Boolean,
      dropdownIcon: String,

      options: {
        type: Array,
        default: function () { return []; }
      },

      optionValue: [Function, String],
      optionLabel: [Function, String],
      optionDisable: [Function, String],

      hideSelected: Boolean,
      hideDropdownIcon: Boolean,
      fillInput: Boolean,

      maxValues: [Number, String],

      optionsDense: Boolean,
      optionsDark: {
        type: Boolean,
        default: null
      },
      optionsSelectedClass: String,
      optionsSanitize: Boolean,

      optionsCover: Boolean,

      menuShrink: Boolean,
      menuAnchor: String,
      menuSelf: String,
      menuOffset: Array,

      popupContentClass: String,
      popupContentStyle: [String, Array, Object],

      useInput: Boolean,
      useChips: Boolean,

      newValueMode: {
        type: String,
        validator: validateNewValueMode
      },

      mapOptions: Boolean,
      emitValue: Boolean,

      inputDebounce: {
        type: [Number, String],
        default: 500
      },

      inputClass: [Array, String, Object],
      inputStyle: [Array, String, Object],

      tabindex: {
        type: [String, Number],
        default: 0
      },

      transitionShow: String,
      transitionHide: String,

      behavior: {
        type: String,
        validator: function (v) { return ['default', 'menu', 'dialog'].includes(v); },
        default: 'default'
      }
    },

    data: function data () {
      return {
        menu: false,
        dialog: false,
        optionIndex: -1,
        inputValue: '',
        dialogFieldFocused: false
      }
    },

    watch: {
      innerValue: {
        handler: function handler (val) {
          this.innerValueCache = val;

          if (
            this.useInput === true &&
            this.fillInput === true &&
            this.multiple !== true &&
            // Prevent re-entering in filter while filtering
            // Also prevent clearing inputValue while filtering
            this.innerLoading !== true &&
            ((this.dialog !== true && this.menu !== true) || this.hasValue !== true)
          ) {
            this.__resetInputValue();
            if (this.dialog === true || this.menu === true) {
              this.filter('');
            }
          }
        },
        immediate: true
      },

      fillInput: function fillInput () {
        this.__resetInputValue();
      },

      menu: function menu (show) {
        this.__updateMenu(show);
      }
    },

    computed: {
      isOptionsDark: function isOptionsDark () {
        return this.optionsDark === null
          ? this.isDark
          : this.optionsDark
      },

      virtualScrollLength: function virtualScrollLength () {
        return Array.isArray(this.options)
          ? this.options.length
          : 0
      },

      fieldClass: function fieldClass () {
        return ("q-select q-field--auto-height q-select--with" + (this.useInput !== true ? 'out' : '') + "-input")
      },

      computedInputClass: function computedInputClass () {
        if (this.hideSelected === true || this.innerValue.length === 0) {
          return this.inputClass
        }

        return this.inputClass === void 0
          ? 'q-field__input--padding'
          : [this.inputClass, 'q-field__input--padding']
      },

      menuContentClass: function menuContentClass () {
        return (this.virtualScrollHorizontal === true ? 'q-virtual-scroll--horizontal' : '') +
          (this.popupContentClass ? ' ' + this.popupContentClass : '')
      },

      innerValue: function innerValue () {
        var this$1 = this;

        var
          mapNull = this.mapOptions === true && this.multiple !== true,
          val = this.value !== void 0 && (this.value !== null || mapNull === true)
            ? (this.multiple === true && Array.isArray(this.value) ? this.value : [ this.value ])
            : [];

        if (this.mapOptions === true && Array.isArray(this.options) === true) {
          var cache = this.mapOptions === true && this.innerValueCache !== void 0
            ? this.innerValueCache
            : [];
          var values = val.map(function (v) { return this$1.__getOption(v, cache); });

          return this.value === null && mapNull === true
            ? values.filter(function (v) { return v !== null; })
            : values
        }

        return val
      },

      noOptions: function noOptions () {
        return this.virtualScrollLength === 0
      },

      selectedString: function selectedString () {
        var this$1 = this;

        return this.innerValue
          .map(function (opt) { return this$1.getOptionLabel(opt); })
          .join(', ')
      },

      sanitizeFn: function sanitizeFn () {
        return this.optionsSanitize === true
          ? function () { return true; }
          : function (opt) { return opt !== void 0 && opt !== null && opt.sanitize === true; }
      },

      displayAsText: function displayAsText () {
        return this.displayValueSanitize === true || (
          this.displayValue === void 0 && (
            this.optionsSanitize === true ||
            this.innerValue.some(this.sanitizeFn)
          )
        )
      },

      computedTabindex: function computedTabindex () {
        return this.focused === true ? this.tabindex : -1
      },

      selectedScope: function selectedScope () {
        var this$1 = this;

        return this.innerValue.map(function (opt, i) { return ({
          index: i,
          opt: opt,
          sanitize: this$1.sanitizeFn(opt),
          selected: true,
          removeAtIndex: this$1.__removeAtIndexAndFocus,
          toggleOption: this$1.toggleOption,
          tabindex: this$1.computedTabindex
        }); })
      },

      optionScope: function optionScope () {
        var this$1 = this;

        if (this.virtualScrollLength === 0) {
          return []
        }

        var ref = this.virtualScrollSliceRange;
        var from = ref.from;
        var to = ref.to;

        return this.options.slice(from, to).map(function (opt, i) {
          var disable = this$1.isOptionDisabled(opt) === true;
          var index = from + i;

          var itemProps = {
            clickable: true,
            active: false,
            activeClass: this$1.computedOptionsSelectedClass,
            manualFocus: true,
            focused: false,
            disable: disable,
            tabindex: -1,
            dense: this$1.optionsDense,
            dark: this$1.isOptionsDark
          };

          if (disable !== true) {
            this$1.isOptionSelected(opt) === true && (itemProps.active = true);
            this$1.optionIndex === index && (itemProps.focused = true);
          }

          var itemEvents = {
            click: function () { this$1.toggleOption(opt); }
          };

          if (this$1.$q.platform.is.desktop === true) {
            itemEvents.mousemove = function () { this$1.setOptionIndex(index); };
          }

          return {
            index: index,
            opt: opt,
            sanitize: this$1.sanitizeFn(opt),
            selected: itemProps.active,
            focused: itemProps.focused,
            toggleOption: this$1.toggleOption,
            setOptionIndex: this$1.setOptionIndex,
            itemProps: itemProps,
            itemEvents: itemEvents
          }
        })
      },

      dropdownArrowIcon: function dropdownArrowIcon () {
        return this.dropdownIcon !== void 0
          ? this.dropdownIcon
          : this.$q.iconSet.arrow.dropdown
      },

      squaredMenu: function squaredMenu () {
        return this.optionsCover === false &&
          this.outlined !== true &&
          this.standout !== true &&
          this.borderless !== true &&
          this.rounded !== true
      },

      computedOptionsSelectedClass: function computedOptionsSelectedClass () {
        return this.optionsSelectedClass !== void 0
          ? this.optionsSelectedClass
          : (this.color !== void 0 ? ("text-" + (this.color)) : '')
      },

      innerOptionsValue: function innerOptionsValue () {
        var this$1 = this;

        return this.innerValue.map(function (opt) { return this$1.getOptionValue(opt); })
      },

      // returns method to get value of an option;
      // takes into account 'option-value' prop
      getOptionValue: function getOptionValue () {
        return this.__getPropValueFn('optionValue', 'value')
      },

      // returns method to get label of an option;
      // takes into account 'option-label' prop
      getOptionLabel: function getOptionLabel () {
        return this.__getPropValueFn('optionLabel', 'label')
      },

      // returns method to tell if an option is disabled;
      // takes into account 'option-disable' prop
      isOptionDisabled: function isOptionDisabled () {
        return this.__getPropValueFn('optionDisable', 'disable')
      }
    },

    methods: {
      getEmittingOptionValue: function getEmittingOptionValue (opt) {
        return this.emitValue === true
          ? this.getOptionValue(opt)
          : opt
      },

      removeAtIndex: function removeAtIndex (index) {
        if (index > -1 && index < this.innerValue.length) {
          if (this.multiple === true) {
            var model = this.value.slice();
            this.$emit('remove', { index: index, value: model.splice(index, 1) });
            this.$emit('input', model);
          }
          else {
            this.$emit('input', null);
          }
        }
      },

      __removeAtIndexAndFocus: function __removeAtIndexAndFocus (index) {
        this.removeAtIndex(index);
        this.__focus();
      },

      add: function add (opt, unique) {
        var val = this.getEmittingOptionValue(opt);

        if (this.multiple !== true) {
          this.fillInput === true && this.updateInputValue(
            this.getOptionLabel(opt),
            true,
            true
          );

          this.$emit('input', val);
          return
        }

        if (this.innerValue.length === 0) {
          this.$emit('add', { index: 0, value: val });
          this.$emit('input', this.multiple === true ? [ val ] : val);
          return
        }

        if (unique === true && this.isOptionSelected(opt) === true) {
          return
        }

        if (this.maxValues !== void 0 && this.value.length >= this.maxValues) {
          return
        }

        var model = this.value.slice();

        this.$emit('add', { index: model.length, value: val });
        model.push(val);
        this.$emit('input', model);
      },

      toggleOption: function toggleOption (opt, keepOpen) {
        if (this.editable !== true || opt === void 0 || this.isOptionDisabled(opt) === true) {
          return
        }

        var optValue = this.getOptionValue(opt);

        if (this.multiple !== true) {
          this.$refs.target !== void 0 && this.$refs.target.focus();

          if (keepOpen !== true) {
            this.updateInputValue(
              this.fillInput === true ? this.getOptionLabel(opt) : '',
              true,
              true
            );

            this.hidePopup();
          }

          if (isDeepEqual(this.getOptionValue(this.innerValue), optValue) !== true) {
            this.$emit('input', this.emitValue === true ? optValue : opt);
          }
          return
        }

        (this.hasDialog !== true || this.dialogFieldFocused === true) && this.__focus();

        this.__selectInputText();

        if (this.innerValue.length === 0) {
          var val = this.emitValue === true ? optValue : opt;
          this.$emit('add', { index: 0, value: val });
          this.$emit('input', this.multiple === true ? [ val ] : val);
          return
        }

        var
          model = this.value.slice(),
          index = this.innerOptionsValue.findIndex(function (v) { return isDeepEqual(v, optValue); });

        if (index > -1) {
          this.$emit('remove', { index: index, value: model.splice(index, 1) });
        }
        else {
          if (this.maxValues !== void 0 && model.length >= this.maxValues) {
            return
          }

          var val$1 = this.emitValue === true ? optValue : opt;

          this.$emit('add', { index: model.length, value: val$1 });
          model.push(val$1);
        }

        this.$emit('input', model);
      },

      setOptionIndex: function setOptionIndex (index) {
        if (this.$q.platform.is.desktop !== true) { return }

        var val = index > -1 && index < this.virtualScrollLength
          ? index
          : -1;

        if (this.optionIndex !== val) {
          this.optionIndex = val;
        }
      },

      moveOptionSelection: function moveOptionSelection (offset, skipInputValue) {
        if ( offset === void 0 ) offset = 1;

        if (this.menu === true) {
          var index = this.optionIndex;
          do {
            index = normalizeToInterval(
              index + offset,
              -1,
              this.virtualScrollLength - 1
            );
          }
          while (index !== -1 && index !== this.optionIndex && this.isOptionDisabled(this.options[index]) === true)

          if (this.optionIndex !== index) {
            this.setOptionIndex(index);
            this.scrollTo(index);

            if (skipInputValue !== true && index >= 0 && this.useInput === true && this.fillInput === true) {
              var inputValue = this.getOptionLabel(this.options[index]);
              if (this.inputValue !== inputValue) {
                this.inputValue = inputValue;
              }
            }
          }
        }
      },

      __getOption: function __getOption (value, innerValueCache) {
        var this$1 = this;

        var fn = function (opt) { return isDeepEqual(this$1.getOptionValue(opt), value); };
        return this.options.find(fn) || innerValueCache.find(fn) || value
      },

      __getPropValueFn: function __getPropValueFn (propName, defaultVal) {
        var val = this[propName] !== void 0
          ? this[propName]
          : defaultVal;

        return typeof val === 'function'
          ? val
          : function (opt) { return Object(opt) === opt && val in opt
            ? opt[val]
            : opt; }
      },

      isOptionSelected: function isOptionSelected (opt) {
        var val = this.getOptionValue(opt);
        return this.innerOptionsValue.find(function (v) { return isDeepEqual(v, val); }) !== void 0
      },

      __selectInputText: function __selectInputText () {
        if (this.useInput === true && this.$refs.target !== void 0) {
          this.$refs.target.select();
        }
      },

      __onTargetKeyup: function __onTargetKeyup (e) {
        // if ESC and we have an opened menu
        // then stop propagation (might be caught by a QDialog
        // and so it will also close the QDialog, which is wrong)
        if (isKeyCode(e, 27) === true && this.menu === true) {
          stop(e);
          // on ESC we need to close the dialog also
          this.hidePopup();
        }

        this.$emit('keyup', e);
      },

      __onTargetAutocomplete: function __onTargetAutocomplete (e) {
        var this$1 = this;

        var ref = e.target;
        var value = ref.value;

        e.target.value = '';

        if (
          e.keyCode === void 0 &&
          typeof value === 'string' &&
          value.length > 0
        ) {
          var needle = value.toLocaleLowerCase();

          var fn = function (opt) { return this$1.getOptionValue(opt).toLocaleLowerCase() === needle; };
          var option = this.options.find(fn);

          if (option !== null) {
            this.innerValue.indexOf(option) === -1 && this.toggleOption(option);
          }
          else {
            fn = function (opt) { return this$1.getOptionLabel(opt).toLocaleLowerCase() === needle; };
            option = this.options.find(fn);

            if (option !== null) {
              this.innerValue.indexOf(option) === -1 && this.toggleOption(option);
            }
          }
        }
      },

      __onTargetKeypress: function __onTargetKeypress (e) {
        this.$emit('keypress', e);
      },

      __onTargetKeydown: function __onTargetKeydown (e) {
        var this$1 = this;

        this.$emit('keydown', e);

        if (shouldIgnoreKey(e) === true) {
          return
        }

        var newValueModeValid = this.inputValue.length > 0 &&
          (this.newValueMode !== void 0 || this.$listeners['new-value'] !== void 0);
        var tabShouldSelect = e.shiftKey !== true &&
          this.multiple !== true &&
          (this.optionIndex > -1 || newValueModeValid === true);

        // escape
        if (e.keyCode === 27) {
          prevent(e); // prevent clearing the inputValue
          return
        }

        // tab
        if (e.keyCode === 9 && tabShouldSelect === false) {
          this.__closeMenu();
          return
        }

        if (e.target === void 0 || e.target.id !== this.targetUid) { return }

        // down
        if (
          e.keyCode === 40 &&
          this.innerLoading !== true &&
          this.menu === false
        ) {
          stopAndPrevent(e);
          this.showPopup();
          return
        }

        // backspace
        if (
          e.keyCode === 8 &&
          this.multiple === true &&
          this.inputValue.length === 0 &&
          Array.isArray(this.value)
        ) {
          this.removeAtIndex(this.value.length - 1);
          return
        }

        // up, down
        if (e.keyCode === 38 || e.keyCode === 40) {
          stopAndPrevent(e);
          this.moveOptionSelection(e.keyCode === 38 ? -1 : 1, this.multiple);
        }

        var optionsLength = this.virtualScrollLength;

        // keyboard search when not having use-input
        if (optionsLength > 0 && this.useInput !== true && e.keyCode >= 48 && e.keyCode <= 90) {
          this.menu !== true && this.showPopup(e);

          // clear search buffer if expired
          if (this.searchBuffer === void 0 || this.searchBufferExp < Date.now()) {
            this.searchBuffer = '';
          }

          var
            char = String.fromCharCode(e.keyCode).toLocaleLowerCase(),
            keyRepeat = this.searchBuffer.length === 1 && this.searchBuffer[0] === char;

          this.searchBufferExp = Date.now() + 1500;
          if (keyRepeat === false) {
            this.searchBuffer += char;
          }

          var searchRe = new RegExp('^' + this.searchBuffer.split('').join('.*'), 'i');

          var index = this.optionIndex;

          if (keyRepeat === true || searchRe.test(this.getOptionLabel(this.options[index])) !== true) {
            do {
              index = normalizeToInterval(index + 1, -1, optionsLength - 1);
            }
            while (index !== this.optionIndex && (
              this.isOptionDisabled(this.options[index]) === true ||
              searchRe.test(this.getOptionLabel(this.options[index])) !== true
            ))
          }

          if (this.optionIndex !== index) {
            this.$nextTick(function () {
              this$1.setOptionIndex(index);
              this$1.scrollTo(index);

              if (index >= 0 && this$1.useInput === true && this$1.fillInput === true) {
                var inputValue = this$1.getOptionLabel(this$1.options[index]);
                if (this$1.inputValue !== inputValue) {
                  this$1.inputValue = inputValue;
                }
              }
            });
          }

          return
        }

        // enter, space (when not using use-input), or tab (when not using multiple and option selected)
        // same target is checked above
        if (
          e.keyCode !== 13 &&
          (this.useInput === true || e.keyCode !== 32) &&
          (tabShouldSelect === false || e.keyCode !== 9)
        ) { return }

        e.keyCode !== 9 && stopAndPrevent(e);

        if (this.optionIndex > -1 && this.optionIndex < optionsLength) {
          this.toggleOption(this.options[this.optionIndex]);
          return
        }

        if (newValueModeValid === true) {
          var done = function (val, mode) {
            if (mode) {
              if (validateNewValueMode(mode) !== true) {
                console.error('QSelect: invalid new value mode - ' + mode);
                return
              }
            }
            else {
              mode = this$1.newValueMode;
            }

            if (val === void 0 || val === null) {
              return
            }

            this$1.updateInputValue('', this$1.multiple !== true, true);

            this$1[mode === 'toggle' ? 'toggleOption' : 'add'](
              val,
              mode === 'add-unique'
            );

            if (this$1.multiple !== true) {
              this$1.$refs.target !== void 0 && this$1.$refs.target.focus();
              this$1.hidePopup();
            }
          };

          if (this.$listeners['new-value'] !== void 0) {
            this.$emit('new-value', this.inputValue, done);
          }
          else {
            done(this.inputValue);
          }

          if (this.multiple !== true) {
            return
          }
        }

        if (this.menu === true) {
          this.__closeMenu();
        }
        else if (this.innerLoading !== true) {
          this.showPopup();
        }
      },

      __getVirtualScrollEl: function __getVirtualScrollEl () {
        return this.hasDialog === true
          ? this.$refs.menuContent
          : (
            this.$refs.menu !== void 0 && this.$refs.menu.__portal !== void 0
              ? this.$refs.menu.__portal.$el
              : void 0
          )
      },

      __getVirtualScrollTarget: function __getVirtualScrollTarget () {
        return this.__getVirtualScrollEl()
      },

      __getSelection: function __getSelection (h, fromDialog) {
        var this$1 = this;
        var obj;

        if (this.hideSelected === true) {
          return fromDialog !== true && this.hasDialog === true
            ? [
              h('span', {
                domProps: {
                  textContent: this.inputValue
                }
              })
            ]
            : []
        }

        if (this.$scopedSlots['selected-item'] !== void 0) {
          return this.selectedScope.map(function (scope) { return this$1.$scopedSlots['selected-item'](scope); }).slice()
        }

        if (this.$scopedSlots.selected !== void 0) {
          return this.$scopedSlots.selected().slice()
        }

        if (this.useChips === true) {
          return this.selectedScope.map(function (scope, i) {
            var obj;

            return h(QChip, {
            key: 'option-' + i,
            props: {
              removable: this$1.isOptionDisabled(scope.opt) !== true,
              dense: true,
              textColor: this$1.color,
              tabindex: this$1.computedTabindex
            },
            on: cache(this$1, 'rem#' + i, {
              remove: function remove () { scope.removeAtIndex(i); }
            })
          }, [
            h('span', {
              domProps: ( obj = {}, obj[scope.sanitize === true ? 'textContent' : 'innerHTML'] = this$1.getOptionLabel(scope.opt), obj )
            })
          ]);
          })
        }

        return [
          h('span', {
            domProps: ( obj = {}, obj[this.displayAsText ? 'textContent' : 'innerHTML'] = this.displayValue !== void 0
                ? this.displayValue
                : this.selectedString, obj )
          })
        ]
      },

      __getControl: function __getControl (h, fromDialog) {
        var child = this.__getSelection(h, fromDialog);

        if (this.useInput === true && (fromDialog === true || this.hasDialog === false)) {
          child.push(this.__getInput(h, fromDialog));
        }
        else if (this.editable === true) {
          var isShadowField = this.hasDialog === true && fromDialog !== true && this.menu === true;

          if (fromDialog !== true) {
            child.push(h('input', {
              staticClass: 'q-select__autocomplete-input no-outline',
              attrs: {
                autocomplete: this.$attrs.autocomplete,
                tabindex: -1
              },
              on: cache(this, 'acpl', {
                keyup: this.__onTargetAutocomplete
              })
            }));
          }

          child.push(h('div', {
            // there can be only one (when dialog is opened the control in dialog should be target)
            ref: isShadowField === true ? void 0 : 'target',
            staticClass: 'no-outline',
            attrs: {
              tabindex: this.tabindex,
              id: isShadowField === true ? void 0 : this.targetUid
            },
            on: cache(this, 'ctrl', {
              keydown: this.__onTargetKeydown,
              keyup: this.__onTargetKeyup,
              keypress: this.__onTargetKeypress
            })
          }));
        }

        if (this.nameProp !== void 0 && this.disable !== true && this.innerOptionsValue.length > 0) {
          var opts = this.innerOptionsValue.map(function (value) { return h('option', {
            attrs: { value: value, selected: true }
          }); });

          child.push(
            h('select', {
              staticClass: 'hidden',
              attrs: {
                name: this.nameProp,
                multiple: this.multiple
              }
            }, opts)
          );
        }

        return h('div', { staticClass: 'q-field__native row items-center', attrs: this.$attrs }, child)
      },

      __getOptions: function __getOptions (h) {
        var this$1 = this;

        if (this.menu !== true) {
          return void 0
        }

        var fn = this.$scopedSlots.option !== void 0
          ? this.$scopedSlots.option
          : function (scope) {
            var obj;

            return h(QItem, {
            key: scope.index,
            props: scope.itemProps,
            on: scope.itemEvents
          }, [
            h(QItemSection, [
              h(QItemLabel, {
                domProps: ( obj = {}, obj[scope.sanitize === true ? 'textContent' : 'innerHTML'] = this$1.getOptionLabel(scope.opt), obj )
              })
            ])
          ]);
        };

        var options = this.__padVirtualScroll(h, 'div', this.optionScope.map(fn));

        if (this.$scopedSlots['before-options'] !== void 0) {
          options = this.$scopedSlots['before-options']().concat(options);
        }

        return mergeSlot(options, this, 'after-options')
      },

      __getInnerAppend: function __getInnerAppend (h) {
        return this.loading !== true && this.innerLoading !== true && this.hideDropdownIcon !== true
          ? [
            h(QIcon, {
              staticClass: 'q-select__dropdown-icon',
              props: { name: this.dropdownArrowIcon }
            })
          ]
          : null
      },

      __getInput: function __getInput (h, fromDialog) {
        var on = {
          input: this.__onInput,
          // Safari < 10.2 & UIWebView doesn't fire compositionend when
          // switching focus before confirming composition choice
          // this also fixes the issue where some browsers e.g. iOS Chrome
          // fires "change" instead of "input" on autocomplete.
          change: this.__onChange,
          keydown: this.__onTargetKeydown,
          keyup: this.__onTargetKeyup,
          keypress: this.__onTargetKeypress,
          focus: this.__selectInputText
        };

        on.compositionstart = on.compositionupdate = on.compositionend = this.__onComposition;

        if (this.hasDialog === true) {
          on.click = stop;
        }

        return h('input', {
          ref: 'target',
          staticClass: 'q-field__input q-placeholder col',
          style: this.inputStyle,
          class: this.computedInputClass,
          domProps: { value: this.inputValue !== void 0 ? this.inputValue : '' },
          attrs: Object.assign({}, {type: 'search'},
            this.$attrs,
            {tabindex: this.tabindex,
            'data-autofocus': fromDialog === true ? false : this.autofocus,
            id: this.targetUid,
            disabled: this.disable === true,
            readonly: this.readonly === true}),
          on: cache(this, 'inp#' + this.hasDialog, on)
        })
      },

      __onChange: function __onChange (e) {
        this.__onComposition(e);
      },

      __onInput: function __onInput (e) {
        var this$1 = this;

        clearTimeout(this.inputTimer);

        if (e && e.target && e.target.composing === true) {
          return
        }

        this.inputValue = e.target.value || '';
        // mark it here as user input so that if updateInputValue is called
        // before filter is called the indicator is reset
        this.userInputValue = true;

        if (
          this.focused !== true &&
          (this.hasDialog !== true || this.dialogFieldFocused === true)
        ) {
          this.__focus();
        }

        if (this.$listeners.filter !== void 0) {
          this.inputTimer = setTimeout(function () {
            this$1.filter(this$1.inputValue);
          }, this.inputDebounce);
        }
      },

      updateInputValue: function updateInputValue (val, noFiltering, internal) {
        this.userInputValue = internal !== true;

        if (this.useInput === true) {
          if (this.inputValue !== val) {
            this.inputValue = val;
          }

          noFiltering !== true && this.filter(val);
        }
      },

      filter: function filter (val) {
        var this$1 = this;

        if (this.$listeners.filter === void 0 || this.focused !== true) {
          return
        }

        if (this.innerLoading === true) {
          this.$emit('filter-abort');
        }
        else {
          this.innerLoading = true;
        }

        if (
          val !== '' &&
          this.multiple !== true &&
          this.innerValue.length > 0 &&
          this.userInputValue !== true &&
          val === this.getOptionLabel(this.innerValue[0])
        ) {
          val = '';
        }

        var filterId = setTimeout(function () {
          this$1.menu === true && (this$1.menu = false);
        }, 10);
        clearTimeout(this.filterId);
        this.filterId = filterId;

        this.$emit(
          'filter',
          val,
          function (fn, afterFn) {
            if (this$1.focused === true && this$1.filterId === filterId) {
              clearTimeout(this$1.filterId);

              typeof fn === 'function' && fn();

              this$1.$nextTick(function () {
                this$1.innerLoading = false;
                if (this$1.menu === true) {
                  this$1.__updateMenu(true);
                }
                else {
                  this$1.menu = true;
                }

                typeof afterFn === 'function' && this$1.$nextTick(function () { afterFn(this$1); });
              });
            }
          },
          function () {
            if (this$1.focused === true && this$1.filterId === filterId) {
              clearTimeout(this$1.filterId);
              this$1.innerLoading = false;
            }
            this$1.menu === true && (this$1.menu = false);
          }
        );
      },

      __getControlEvents: function __getControlEvents () {
        var this$1 = this;

        var focusout = function (e) {
          this$1.__onControlFocusout(e, function () {
            this$1.__resetInputValue();
            this$1.__closeMenu();
          });
        };

        return {
          focusin: this.__onControlFocusin,
          focusout: focusout,
          'popup-show': this.__onControlPopupShow,
          'popup-hide': function (e) {
            e !== void 0 && stop(e);
            this$1.$emit('popup-hide', e);
            this$1.hasPopupOpen = false;
            focusout(e);
          },
          click: function (e) {
            if (this$1.hasDialog !== true) {
              // label from QField will propagate click on the input (except IE)
              if (
                (this$1.useInput === true && e.target.classList.contains('q-field__input') !== true) ||
                (this$1.useInput !== true && e.target.classList.contains('no-outline') === true)
              ) {
                return
              }

              if (this$1.menu === true) {
                this$1.__closeMenu();
                this$1.$refs.target !== void 0 && this$1.$refs.target.focus();
                return
              }
            }

            this$1.showPopup(e);
          }
        }
      },

      __getControlChild: function __getControlChild (h) {
        if (
          this.editable !== false && (
            this.dialog === true || // dialog always has menu displayed, so need to render it
            this.noOptions !== true ||
            this.$scopedSlots['no-option'] !== void 0
          )
        ) {
          return this[("__get" + (this.hasDialog === true ? 'Dialog' : 'Menu'))](h)
        }
      },

      __getMenu: function __getMenu (h) {
        var child = this.noOptions === true
          ? (
            this.$scopedSlots['no-option'] !== void 0
              ? this.$scopedSlots['no-option']({ inputValue: this.inputValue })
              : null
          )
          : this.__getOptions(h);

        return h(QMenu, {
          ref: 'menu',
          props: {
            value: this.menu,
            fit: this.menuShrink !== true,
            cover: this.optionsCover === true && this.noOptions !== true && this.useInput !== true,
            anchor: this.menuAnchor,
            self: this.menuSelf,
            offset: this.menuOffset,
            contentClass: this.menuContentClass,
            contentStyle: this.popupContentStyle,
            dark: this.isOptionsDark,
            noParentEvent: true,
            noRefocus: true,
            noFocus: true,
            square: this.squaredMenu,
            transitionShow: this.transitionShow,
            transitionHide: this.transitionHide,
            separateClosePopup: true
          },
          on: cache(this, 'menu', {
            '&scroll': this.__onVirtualScrollEvt,
            'before-hide': this.__closeMenu
          })
        }, child)
      },

      __onDialogFieldFocus: function __onDialogFieldFocus (e) {
        stop(e);
        this.$refs.target !== void 0 && this.$refs.target.focus();
        this.dialogFieldFocused = true;
        window.scrollTo(window.pageXOffset || window.scrollX || document.body.scrollLeft || 0, 0);
      },

      __onDialogFieldBlur: function __onDialogFieldBlur (e) {
        var this$1 = this;

        stop(e);
        this.$nextTick(function () {
          this$1.dialogFieldFocused = false;
        });
      },

      __getDialog: function __getDialog (h) {
        var this$1 = this;

        var content = [
          h(QField, {
            staticClass: ("col-auto " + (this.fieldClass)),
            props: Object.assign({}, this.$props,
              {for: this.targetUid,
              dark: this.isOptionsDark,
              square: true,
              loading: this.innerLoading,
              filled: true,
              stackLabel: this.inputValue.length > 0}),
            on: Object.assign({}, this.$listeners,
              {focus: this.__onDialogFieldFocus,
              blur: this.__onDialogFieldBlur}),
            scopedSlots: Object.assign({}, this.$scopedSlots,
              {rawControl: function () { return this$1.__getControl(h, true); },
              before: void 0,
              after: void 0})
          })
        ];

        this.menu === true && content.push(
          h('div', {
            ref: 'menuContent',
            staticClass: 'scroll',
            class: this.menuContentClass,
            style: this.popupContentStyle,
            on: cache(this, 'virtMenu', {
              click: prevent,
              '&scroll': this.__onVirtualScrollEvt
            })
          }, (
            this.noOptions === true
              ? (
                this.$scopedSlots['no-option'] !== void 0
                  ? this.$scopedSlots['no-option']({ inputValue: this.inputValue })
                  : null
              )
              : this.__getOptions(h)
          ))
        );

        return h(QDialog, {
          ref: 'dialog',
          props: {
            value: this.dialog,
            dark: this.isOptionsDark,
            position: this.useInput === true ? 'top' : void 0,
            transitionShow: this.transitionShowComputed,
            transitionHide: this.transitionHide
          },
          on: cache(this, 'dialog', {
            'before-hide': this.__onDialogBeforeHide,
            hide: this.__onDialogHide,
            show: this.__onDialogShow
          })
        }, [
          h('div', {
            staticClass: 'q-select__dialog' +
              (this.isOptionsDark === true ? ' q-select__dialog--dark q-dark' : '') +
              (this.dialogFieldFocused === true ? ' q-select__dialog--focused' : '')
          }, content)
        ])
      },

      __onDialogBeforeHide: function __onDialogBeforeHide () {
        this.$refs.dialog.__refocusTarget = this.$el.querySelector('.q-field__native > [tabindex]:last-child');
        this.focused = false;
      },

      __onDialogHide: function __onDialogHide (e) {
        this.hidePopup();
        this.$emit('blur', e);
        this.__resetInputValue();
      },

      __onDialogShow: function __onDialogShow () {
        var el = document.activeElement;
        // IE can have null document.activeElement
        if (
          (el === null || el.id !== this.targetUid) &&
          this.$refs.target !== el &&
          this.$refs.target !== void 0
        ) {
          this.$refs.target.focus();
        }
      },

      __closeMenu: function __closeMenu () {
        if (this.dialog === true) {
          return
        }

        if (this.menu === true) {
          this.menu = false;
        }

        if (this.focused === false) {
          clearTimeout(this.filterId);
          this.filterId = void 0;

          if (this.innerLoading === true) {
            this.$emit('filter-abort');
            this.innerLoading = false;
          }
        }
      },

      showPopup: function showPopup (e) {
        if (this.hasDialog === true) {
          this.__onControlFocusin(e);
          this.dialog = true;
        }
        else {
          this.__focus();
        }

        if (this.$listeners.filter !== void 0) {
          this.filter(this.inputValue);
        }
        else if (this.noOptions !== true || this.$scopedSlots['no-option'] !== void 0) {
          this.menu = true;
        }
      },

      hidePopup: function hidePopup () {
        this.dialog = false;
        this.__closeMenu();
      },

      __resetInputValue: function __resetInputValue () {
        this.useInput === true && this.updateInputValue(
          this.multiple !== true && this.fillInput === true && this.innerValue.length > 0
            ? this.getOptionLabel(this.innerValue[0]) || ''
            : '',
          true,
          true
        );
      },

      __updateMenu: function __updateMenu (show) {
        var this$1 = this;

        var optionIndex = -1;

        if (show === true) {
          if (this.innerValue.length > 0) {
            var val = this.getOptionValue(this.innerValue[0]);
            optionIndex = this.options.findIndex(function (v) { return isDeepEqual(this$1.getOptionValue(v), val); });
          }

          this.__resetVirtualScroll(optionIndex);
        }

        this.setOptionIndex(optionIndex);
      },

      __onPreRender: function __onPreRender () {
        this.hasDialog = this.$q.platform.is.mobile !== true && this.behavior !== 'dialog'
          ? false
          : this.behavior !== 'menu' && (
            this.useInput === true
              ? this.$scopedSlots['no-option'] !== void 0 || this.$listeners.filter !== void 0 || this.noOptions === false
              : true
          );

        this.transitionShowComputed = this.hasDialog === true && this.useInput === true && this.$q.platform.is.ios === true
          ? 'fade'
          : this.transitionShow;
      },

      __onPostRender: function __onPostRender () {
        if (this.dialog === false && this.$refs.menu !== void 0) {
          this.$refs.menu.updatePosition();
        }
      },

      updateMenuPosition: function updateMenuPosition () {
        this.__onPostRender();
      }
    },

    beforeDestroy: function beforeDestroy () {
      clearTimeout(this.inputTimer);
    }
  });

  var skeletonTypes = [
    'text', 'rect', 'circle',
    'QBtn', 'QBadge', 'QChip', 'QToolbar',
    'QCheckbox', 'QRadio', 'QToggle',
    'QSlider', 'QRange', 'QInput',
    'QAvatar'
  ];

  var skeletonAnimations = [
    'wave', 'pulse', 'pulse-x', 'pulse-y', 'fade', 'blink', 'none'
  ];

  var QSkeleton = Vue.extend({
    name: 'QSkeleton',

    mixins: [ DarkMixin, TagMixin ],

    props: {
      type: {
        type: String,
        validator: function (v) { return skeletonTypes.includes(v); },
        default: 'rect'
      },

      animation: {
        type: String,
        validator: function (v) { return skeletonAnimations.includes(v); },
        default: 'wave'
      },

      square: Boolean,
      bordered: Boolean,

      size: String,
      width: String,
      height: String
    },

    computed: {
      style: function style () {
        return this.size !== void 0
          ? { width: this.size, height: this.size }
          : { width: this.width, height: this.height }
      },

      classes: function classes () {
        return "q-skeleton--" + (this.isDark === true ? 'dark' : 'light') + " q-skeleton--type-" + (this.type) +
          (this.animation !== 'none' ? (" q-skeleton--anim-" + (this.animation)) : '') +
          (this.square === true ? ' q-skeleton--square' : '') +
          (this.bordered === true ? ' q-skeleton--bordered' : '')
      }
    },

    render: function render (h) {
      return h(this.tag, {
        staticClass: 'q-skeleton',
        class: this.classes,
        style: this.style,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var slotsDef = [
    ['left', 'center', 'start', 'width'],
    ['right', 'center', 'end', 'width'],
    ['top', 'start', 'center', 'height'],
    ['bottom', 'end', 'center', 'height']
  ];

  var QSlideItem = Vue.extend({
    name: 'QSlideItem',

    mixins: [ DarkMixin ],

    props: {
      leftColor: String,
      rightColor: String,
      topColor: String,
      bottomColor: String
    },

    directives: {
      TouchPan: TouchPan
    },

    computed: {
      langDir: function langDir () {
        return this.$q.lang.rtl === true
          ? { left: 'right', right: 'left' }
          : { left: 'left', right: 'right' }
      }
    },

    methods: {
      reset: function reset () {
        this.$refs.content.style.transform = "translate(0,0)";
      },

      __pan: function __pan (evt) {
        var this$1 = this;

        var node = this.$refs.content;

        if (evt.isFirst) {
          this.__dir = null;
          this.__size = { left: 0, right: 0, top: 0, bottom: 0 };
          this.__scale = 0;

          node.classList.add('no-transition');

          slotsDef.forEach(function (slot) {
            if (this$1.$scopedSlots[slot[0]] !== void 0) {
              var node = this$1.$refs[slot[0] + 'Content'];
              node.style.transform = "scale(1)";
              this$1.__size[slot[0]] = node.getBoundingClientRect()[slot[3]];
            }
          });

          this.__axis = (evt.direction === 'up' || evt.direction === 'down')
            ? 'Y'
            : 'X';
        }
        else if (evt.isFinal) {
          node.classList.remove('no-transition');

          if (this.__scale === 1) {
            node.style.transform = "translate" + (this.__axis) + "(" + (this.__dir * 100) + "%)";

            this.timer = setTimeout(function () {
              this$1.$emit(this$1.__showing, { reset: this$1.reset });
              this$1.$emit('action', { side: this$1.__showing, reset: this$1.reset });
            }, 230);
          }
          else {
            node.style.transform = "translate(0,0)";
          }

          return
        }
        else {
          evt.direction = this.__axis === 'X'
            ? evt.offset.x < 0 ? 'left' : 'right'
            : evt.offset.y < 0 ? 'up' : 'down';
        }

        if (
          (this.$scopedSlots.left === void 0 && evt.direction === this.langDir.right) ||
          (this.$scopedSlots.right === void 0 && evt.direction === this.langDir.left) ||
          (this.$scopedSlots.top === void 0 && evt.direction === 'down') ||
          (this.$scopedSlots.bottom === void 0 && evt.direction === 'up')
        ) {
          node.style.transform = "translate(0,0)";
          return
        }

        var showing, dir, dist;

        if (this.__axis === 'X') {
          dir = evt.direction === 'left' ? -1 : 1;
          showing = dir === 1 ? this.langDir.left : this.langDir.right;
          dist = evt.distance.x;
        }
        else {
          dir = evt.direction === 'up' ? -2 : 2;
          showing = dir === 2 ? 'top' : 'bottom';
          dist = evt.distance.y;
        }

        if (this.__dir !== null && Math.abs(dir) !== Math.abs(this.__dir)) {
          return
        }

        if (this.__dir !== dir) {
          ['left', 'right', 'top', 'bottom'].forEach(function (d) {
            if (this$1.$refs[d] !== void 0) {
              this$1.$refs[d].style.visibility = showing === d
                ? 'visible'
                : 'hidden';
            }
          });
          this.__showing = showing;
          this.__dir = dir;
        }

        this.__scale = Math.max(0, Math.min(1, (dist - 40) / this.__size[showing]));

        node.style.transform = "translate" + (this.__axis) + "(" + (dist * dir / Math.abs(dir)) + "px)";
        this.$refs[(showing + "Content")].style.transform = "scale(" + (this.__scale) + ")";
      }
    },

    render: function render (h) {
      var this$1 = this;

      var
        content = [],
        left = this.$scopedSlots[this.langDir.right] !== void 0,
        right = this.$scopedSlots[this.langDir.left] !== void 0,
        up = this.$scopedSlots.bottom !== void 0,
        down = this.$scopedSlots.top !== void 0;

      slotsDef.forEach(function (slot) {
        var dir = slot[0];

        if (this$1.$scopedSlots[dir] !== void 0) {
          content.push(
            h('div', {
              ref: dir,
              class: "q-slide-item__" + dir + " absolute-full row no-wrap items-" + (slot[1]) + " justify-" + (slot[2]) +
                (this$1[dir + 'Color'] !== void 0 ? (" bg-" + (this$1[dir + 'Color'])) : '')
            }, [
              h('div', { ref: dir + 'Content' }, this$1.$scopedSlots[dir]())
            ])
          );
        }
      });

      content.push(
        h('div', {
          ref: 'content',
          key: 'content',
          staticClass: 'q-slide-item__content',
          directives: left === true || right === true || up === true || down === true ? [{
            name: 'touch-pan',
            value: this.__pan,
            modifiers: {
              left: left,
              right: right,
              up: up,
              down: down,
              prevent: true,
              stop: true,
              mouse: true
            }
          }] : null
        }, slot(this, 'default'))
      );

      return h('div', {
        staticClass: 'q-slide-item q-item-type overflow-hidden',
        class: this.isDark === true ? "q-slide-item--dark q-dark" : '',
        on: this.$listeners
      }, content)
    },

    beforeDestroy: function beforeDestroy () {
      clearTimeout(this.timer);
    }
  });

  var QSpace = Vue.extend({
    name: 'QSpace',

    render: function render (h) {
      return h('div', {
        staticClass: 'q-space',
        on: this.$listeners
      })
    }
  });

  var QSpinnerAudio = Vue.extend({
    name: 'QSpinnerAudio',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'fill': 'currentColor',
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 55 80',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('g', {
          attrs: {
            'transform': 'matrix(1 0 0 -1 0 80)'
          }
        }, [
          h('rect', {
            attrs: {
              'width': '10',
              'height': '20',
              'rx': '3'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'height',
                'begin': '0s',
                'dur': '4.3s',
                'values': '20;45;57;80;64;32;66;45;64;23;66;13;64;56;34;34;2;23;76;79;20',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('rect', {
            attrs: {
              'x': '15',
              'width': '10',
              'height': '80',
              'rx': '3'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'height',
                'begin': '0s',
                'dur': '2s',
                'values': '80;55;33;5;75;23;73;33;12;14;60;80',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('rect', {
            attrs: {
              'x': '30',
              'width': '10',
              'height': '50',
              'rx': '3'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'height',
                'begin': '0s',
                'dur': '1.4s',
                'values': '50;34;78;23;56;23;34;76;80;54;21;50',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('rect', {
            attrs: {
              'x': '45',
              'width': '10',
              'height': '30',
              'rx': '3'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'height',
                'begin': '0s',
                'dur': '2s',
                'values': '30;45;13;80;56;72;45;76;34;23;67;30',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerBall = Vue.extend({
    name: 'QSpinnerBall',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'stroke': 'currentColor',
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 57 57',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('g', {
          attrs: {
            'transform': 'translate(1 1)',
            'stroke-width': '2',
            'fill': 'none',
            'fill-rule': 'evenodd'
          }
        }, [
          h('circle', {
            attrs: {
              'cx': '5',
              'cy': '50',
              'r': '5'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'cy',
                'begin': '0s',
                'dur': '2.2s',
                'values': '50;5;50;50',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            }),
            h('animate', {
              attrs: {
                'attributeName': 'cx',
                'begin': '0s',
                'dur': '2.2s',
                'values': '5;27;49;5',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('circle', {
            attrs: {
              'cx': '27',
              'cy': '5',
              'r': '5'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'cy',
                'begin': '0s',
                'dur': '2.2s',
                'from': '5',
                'to': '5',
                'values': '5;50;50;5',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            }),
            h('animate', {
              attrs: {
                'attributeName': 'cx',
                'begin': '0s',
                'dur': '2.2s',
                'from': '27',
                'to': '27',
                'values': '27;49;5;27',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('circle', {
            attrs: {
              'cx': '49',
              'cy': '50',
              'r': '5'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'cy',
                'begin': '0s',
                'dur': '2.2s',
                'values': '50;50;5;50',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            }),
            h('animate', {
              attrs: {
                'attributeName': 'cx',
                'from': '49',
                'to': '49',
                'begin': '0s',
                'dur': '2.2s',
                'values': '49;5;27;49',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerBars = Vue.extend({
    name: 'QSpinnerBars',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'fill': 'currentColor',
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 135 140',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('rect', {
          attrs: {
            'y': '10',
            'width': '15',
            'height': '120',
            'rx': '6'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'height',
              'begin': '0.5s',
              'dur': '1s',
              'values': '120;110;100;90;80;70;60;50;40;140;120',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          }),
          h('animate', {
            attrs: {
              'attributeName': 'y',
              'begin': '0.5s',
              'dur': '1s',
              'values': '10;15;20;25;30;35;40;45;50;0;10',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('rect', {
          attrs: {
            'x': '30',
            'y': '10',
            'width': '15',
            'height': '120',
            'rx': '6'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'height',
              'begin': '0.25s',
              'dur': '1s',
              'values': '120;110;100;90;80;70;60;50;40;140;120',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          }),
          h('animate', {
            attrs: {
              'attributeName': 'y',
              'begin': '0.25s',
              'dur': '1s',
              'values': '10;15;20;25;30;35;40;45;50;0;10',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('rect', {
          attrs: {
            'x': '60',
            'width': '15',
            'height': '140',
            'rx': '6'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'height',
              'begin': '0s',
              'dur': '1s',
              'values': '120;110;100;90;80;70;60;50;40;140;120',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          }),
          h('animate', {
            attrs: {
              'attributeName': 'y',
              'begin': '0s',
              'dur': '1s',
              'values': '10;15;20;25;30;35;40;45;50;0;10',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('rect', {
          attrs: {
            'x': '90',
            'y': '10',
            'width': '15',
            'height': '120',
            'rx': '6'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'height',
              'begin': '0.25s',
              'dur': '1s',
              'values': '120;110;100;90;80;70;60;50;40;140;120',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          }),
          h('animate', {
            attrs: {
              'attributeName': 'y',
              'begin': '0.25s',
              'dur': '1s',
              'values': '10;15;20;25;30;35;40;45;50;0;10',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('rect', {
          attrs: {
            'x': '120',
            'y': '10',
            'width': '15',
            'height': '120',
            'rx': '6'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'height',
              'begin': '0.5s',
              'dur': '1s',
              'values': '120;110;100;90;80;70;60;50;40;140;120',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          }),
          h('animate', {
            attrs: {
              'attributeName': 'y',
              'begin': '0.5s',
              'dur': '1s',
              'values': '10;15;20;25;30;35;40;45;50;0;10',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ])
      ])
    }
  });

  var QSpinnerComment = Vue.extend({
    name: 'QSpinnerComment',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'xmlns': 'http://www.w3.org/2000/svg',
          'viewBox': '0 0 100 100',
          'preserveAspectRatio': 'xMidYMid'
        }
      }, [
        h('rect', {
          attrs: {
            'x': '0',
            'y': '0',
            'width': '100',
            'height': '100',
            'fill': 'none'
          }
        }),
        h('path', {
          attrs: {
            'd': 'M78,19H22c-6.6,0-12,5.4-12,12v31c0,6.6,5.4,12,12,12h37.2c0.4,3,1.8,5.6,3.7,7.6c2.4,2.5,5.1,4.1,9.1,4 c-1.4-2.1-2-7.2-2-10.3c0-0.4,0-0.8,0-1.3h8c6.6,0,12-5.4,12-12V31C90,24.4,84.6,19,78,19z',
            'fill': 'currentColor'
          }
        }),
        h('circle', {
          attrs: {
            'cx': '30',
            'cy': '47',
            'r': '5',
            'fill': '#fff'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'opacity',
              'from': '0',
              'to': '1',
              'values': '0;1;1',
              'keyTimes': '0;0.2;1',
              'dur': '1s',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '50',
            'cy': '47',
            'r': '5',
            'fill': '#fff'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'opacity',
              'from': '0',
              'to': '1',
              'values': '0;0;1;1',
              'keyTimes': '0;0.2;0.4;1',
              'dur': '1s',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '70',
            'cy': '47',
            'r': '5',
            'fill': '#fff'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'opacity',
              'from': '0',
              'to': '1',
              'values': '0;0;1;1',
              'keyTimes': '0;0.4;0.6;1',
              'dur': '1s',
              'repeatCount': 'indefinite'
            }
          })
        ])
      ])
    }
  });

  var QSpinnerCube = Vue.extend({
    name: 'QSpinnerCube',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'xmlns': 'http://www.w3.org/2000/svg',
          'viewBox': '0 0 100 100',
          'preserveAspectRatio': 'xMidYMid'
        }
      }, [
        h('rect', {
          attrs: {
            'x': '0',
            'y': '0',
            'width': '100',
            'height': '100',
            'fill': 'none'
          }
        }),
        h('g', {
          attrs: {
            'transform': 'translate(25 25)'
          }
        }, [
          h('rect', {
            attrs: {
              'x': '-20',
              'y': '-20',
              'width': '40',
              'height': '40',
              'fill': 'currentColor',
              'opacity': '0.9'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'scale',
                'from': '1.5',
                'to': '1',
                'repeatCount': 'indefinite',
                'begin': '0s',
                'dur': '1s',
                'calcMode': 'spline',
                'keySplines': '0.2 0.8 0.2 0.8',
                'keyTimes': '0;1'
              }
            })
          ])
        ]),
        h('g', {
          attrs: {
            'transform': 'translate(75 25)'
          }
        }, [
          h('rect', {
            attrs: {
              'x': '-20',
              'y': '-20',
              'width': '40',
              'height': '40',
              'fill': 'currentColor',
              'opacity': '0.8'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'scale',
                'from': '1.5',
                'to': '1',
                'repeatCount': 'indefinite',
                'begin': '0.1s',
                'dur': '1s',
                'calcMode': 'spline',
                'keySplines': '0.2 0.8 0.2 0.8',
                'keyTimes': '0;1'
              }
            })
          ])
        ]),
        h('g', {
          attrs: {
            'transform': 'translate(25 75)'
          }
        }, [
          h('rect', {
            staticClass: 'cube',
            attrs: {
              'x': '-20',
              'y': '-20',
              'width': '40',
              'height': '40',
              'fill': 'currentColor',
              'opacity': '0.7'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'scale',
                'from': '1.5',
                'to': '1',
                'repeatCount': 'indefinite',
                'begin': '0.3s',
                'dur': '1s',
                'calcMode': 'spline',
                'keySplines': '0.2 0.8 0.2 0.8',
                'keyTimes': '0;1'
              }
            })
          ])
        ]),
        h('g', {
          attrs: {
            'transform': 'translate(75 75)'
          }
        }, [
          h('rect', {
            staticClass: 'cube',
            attrs: {
              'x': '-20',
              'y': '-20',
              'width': '40',
              'height': '40',
              'fill': 'currentColor',
              'opacity': '0.6'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'scale',
                'from': '1.5',
                'to': '1',
                'repeatCount': 'indefinite',
                'begin': '0.2s',
                'dur': '1s',
                'calcMode': 'spline',
                'keySplines': '0.2 0.8 0.2 0.8',
                'keyTimes': '0;1'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerDots = Vue.extend({
    name: 'QSpinnerDots',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'fill': 'currentColor',
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 120 30',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('circle', {
          attrs: {
            'cx': '15',
            'cy': '15',
            'r': '15'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'r',
              'from': '15',
              'to': '15',
              'begin': '0s',
              'dur': '0.8s',
              'values': '15;9;15',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          }),
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'from': '1',
              'to': '1',
              'begin': '0s',
              'dur': '0.8s',
              'values': '1;.5;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '60',
            'cy': '15',
            'r': '9',
            'fill-opacity': '.3'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'r',
              'from': '9',
              'to': '9',
              'begin': '0s',
              'dur': '0.8s',
              'values': '9;15;9',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          }),
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'from': '.5',
              'to': '.5',
              'begin': '0s',
              'dur': '0.8s',
              'values': '.5;1;.5',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '105',
            'cy': '15',
            'r': '15'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'r',
              'from': '15',
              'to': '15',
              'begin': '0s',
              'dur': '0.8s',
              'values': '15;9;15',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          }),
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'from': '1',
              'to': '1',
              'begin': '0s',
              'dur': '0.8s',
              'values': '1;.5;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ])
      ])
    }
  });

  var QSpinnerFacebook = Vue.extend({
    name: 'QSpinnerFacebook',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 100 100',
          'xmlns': 'http://www.w3.org/2000/svg',
          'preserveAspectRatio': 'xMidYMid'
        }
      }, [
        h('g', {
          attrs: {
            'transform': 'translate(20 50)'
          }
        }, [
          h('rect', {
            attrs: {
              'x': '-10',
              'y': '-30',
              'width': '20',
              'height': '60',
              'fill': 'currentColor',
              'opacity': '0.6'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'scale',
                'from': '2',
                'to': '1',
                'begin': '0s',
                'repeatCount': 'indefinite',
                'dur': '1s',
                'calcMode': 'spline',
                'keySplines': '0.1 0.9 0.4 1',
                'keyTimes': '0;1',
                'values': '2;1'
              }
            })
          ])
        ]),
        h('g', {
          attrs: {
            'transform': 'translate(50 50)'
          }
        }, [
          h('rect', {
            attrs: {
              'x': '-10',
              'y': '-30',
              'width': '20',
              'height': '60',
              'fill': 'currentColor',
              'opacity': '0.8'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'scale',
                'from': '2',
                'to': '1',
                'begin': '0.1s',
                'repeatCount': 'indefinite',
                'dur': '1s',
                'calcMode': 'spline',
                'keySplines': '0.1 0.9 0.4 1',
                'keyTimes': '0;1',
                'values': '2;1'
              }
            })
          ])
        ]),
        h('g', {
          attrs: {
            'transform': 'translate(80 50)'
          }
        }, [
          h('rect', {
            attrs: {
              'x': '-10',
              'y': '-30',
              'width': '20',
              'height': '60',
              'fill': 'currentColor',
              'opacity': '0.9'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'scale',
                'from': '2',
                'to': '1',
                'begin': '0.2s',
                'repeatCount': 'indefinite',
                'dur': '1s',
                'calcMode': 'spline',
                'keySplines': '0.1 0.9 0.4 1',
                'keyTimes': '0;1',
                'values': '2;1'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerGears = Vue.extend({
    name: 'QSpinnerGears',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 100 100',
          'preserveAspectRatio': 'xMidYMid',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('g', {
          attrs: {
            'transform': 'translate(-20,-20)'
          }
        }, [
          h('path', {
            attrs: {
              'd': 'M79.9,52.6C80,51.8,80,50.9,80,50s0-1.8-0.1-2.6l-5.1-0.4c-0.3-2.4-0.9-4.6-1.8-6.7l4.2-2.9c-0.7-1.6-1.6-3.1-2.6-4.5 L70,35c-1.4-1.9-3.1-3.5-4.9-4.9l2.2-4.6c-1.4-1-2.9-1.9-4.5-2.6L59.8,27c-2.1-0.9-4.4-1.5-6.7-1.8l-0.4-5.1C51.8,20,50.9,20,50,20 s-1.8,0-2.6,0.1l-0.4,5.1c-2.4,0.3-4.6,0.9-6.7,1.8l-2.9-4.1c-1.6,0.7-3.1,1.6-4.5,2.6l2.1,4.6c-1.9,1.4-3.5,3.1-5,4.9l-4.5-2.1 c-1,1.4-1.9,2.9-2.6,4.5l4.1,2.9c-0.9,2.1-1.5,4.4-1.8,6.8l-5,0.4C20,48.2,20,49.1,20,50s0,1.8,0.1,2.6l5,0.4 c0.3,2.4,0.9,4.7,1.8,6.8l-4.1,2.9c0.7,1.6,1.6,3.1,2.6,4.5l4.5-2.1c1.4,1.9,3.1,3.5,5,4.9l-2.1,4.6c1.4,1,2.9,1.9,4.5,2.6l2.9-4.1 c2.1,0.9,4.4,1.5,6.7,1.8l0.4,5.1C48.2,80,49.1,80,50,80s1.8,0,2.6-0.1l0.4-5.1c2.3-0.3,4.6-0.9,6.7-1.8l2.9,4.2 c1.6-0.7,3.1-1.6,4.5-2.6L65,69.9c1.9-1.4,3.5-3,4.9-4.9l4.6,2.2c1-1.4,1.9-2.9,2.6-4.5L73,59.8c0.9-2.1,1.5-4.4,1.8-6.7L79.9,52.6 z M50,65c-8.3,0-15-6.7-15-15c0-8.3,6.7-15,15-15s15,6.7,15,15C65,58.3,58.3,65,50,65z',
              'fill': 'currentColor'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'rotate',
                'from': '90 50 50',
                'to': '0 50 50',
                'dur': '1s',
                'repeatCount': 'indefinite'
              }
            })
          ])
        ]),
        h('g', {
          attrs: {
            'transform': 'translate(20,20) rotate(15 50 50)'
          }
        }, [
          h('path', {
            attrs: {
              'd': 'M79.9,52.6C80,51.8,80,50.9,80,50s0-1.8-0.1-2.6l-5.1-0.4c-0.3-2.4-0.9-4.6-1.8-6.7l4.2-2.9c-0.7-1.6-1.6-3.1-2.6-4.5 L70,35c-1.4-1.9-3.1-3.5-4.9-4.9l2.2-4.6c-1.4-1-2.9-1.9-4.5-2.6L59.8,27c-2.1-0.9-4.4-1.5-6.7-1.8l-0.4-5.1C51.8,20,50.9,20,50,20 s-1.8,0-2.6,0.1l-0.4,5.1c-2.4,0.3-4.6,0.9-6.7,1.8l-2.9-4.1c-1.6,0.7-3.1,1.6-4.5,2.6l2.1,4.6c-1.9,1.4-3.5,3.1-5,4.9l-4.5-2.1 c-1,1.4-1.9,2.9-2.6,4.5l4.1,2.9c-0.9,2.1-1.5,4.4-1.8,6.8l-5,0.4C20,48.2,20,49.1,20,50s0,1.8,0.1,2.6l5,0.4 c0.3,2.4,0.9,4.7,1.8,6.8l-4.1,2.9c0.7,1.6,1.6,3.1,2.6,4.5l4.5-2.1c1.4,1.9,3.1,3.5,5,4.9l-2.1,4.6c1.4,1,2.9,1.9,4.5,2.6l2.9-4.1 c2.1,0.9,4.4,1.5,6.7,1.8l0.4,5.1C48.2,80,49.1,80,50,80s1.8,0,2.6-0.1l0.4-5.1c2.3-0.3,4.6-0.9,6.7-1.8l2.9,4.2 c1.6-0.7,3.1-1.6,4.5-2.6L65,69.9c1.9-1.4,3.5-3,4.9-4.9l4.6,2.2c1-1.4,1.9-2.9,2.6-4.5L73,59.8c0.9-2.1,1.5-4.4,1.8-6.7L79.9,52.6 z M50,65c-8.3,0-15-6.7-15-15c0-8.3,6.7-15,15-15s15,6.7,15,15C65,58.3,58.3,65,50,65z',
              'fill': 'currentColor'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'rotate',
                'from': '0 50 50',
                'to': '90 50 50',
                'dur': '1s',
                'repeatCount': 'indefinite'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerGrid = Vue.extend({
    name: 'QSpinnerGrid',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'fill': 'currentColor',
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 105 105',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('circle', {
          attrs: {
            'cx': '12.5',
            'cy': '12.5',
            'r': '12.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '0s',
              'dur': '1s',
              'values': '1;.2;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '12.5',
            'cy': '52.5',
            'r': '12.5',
            'fill-opacity': '.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '100ms',
              'dur': '1s',
              'values': '1;.2;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '52.5',
            'cy': '12.5',
            'r': '12.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '300ms',
              'dur': '1s',
              'values': '1;.2;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '52.5',
            'cy': '52.5',
            'r': '12.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '600ms',
              'dur': '1s',
              'values': '1;.2;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '92.5',
            'cy': '12.5',
            'r': '12.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '800ms',
              'dur': '1s',
              'values': '1;.2;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '92.5',
            'cy': '52.5',
            'r': '12.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '400ms',
              'dur': '1s',
              'values': '1;.2;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '12.5',
            'cy': '92.5',
            'r': '12.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '700ms',
              'dur': '1s',
              'values': '1;.2;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '52.5',
            'cy': '92.5',
            'r': '12.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '500ms',
              'dur': '1s',
              'values': '1;.2;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('circle', {
          attrs: {
            'cx': '92.5',
            'cy': '92.5',
            'r': '12.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '200ms',
              'dur': '1s',
              'values': '1;.2;1',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ])
      ])
    }
  });

  var QSpinnerHearts = Vue.extend({
    name: 'QSpinnerHearts',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'fill': 'currentColor',
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 140 64',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('path', {
          attrs: {
            'd': 'M30.262 57.02L7.195 40.723c-5.84-3.976-7.56-12.06-3.842-18.063 3.715-6 11.467-7.65 17.306-3.68l4.52 3.76 2.6-5.274c3.716-6.002 11.47-7.65 17.304-3.68 5.84 3.97 7.56 12.054 3.842 18.062L34.49 56.118c-.897 1.512-2.793 1.915-4.228.9z',
            'fill-opacity': '.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '0s',
              'dur': '1.4s',
              'values': '0.5;1;0.5',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('path', {
          attrs: {
            'd': 'M105.512 56.12l-14.44-24.272c-3.716-6.008-1.996-14.093 3.843-18.062 5.835-3.97 13.588-2.322 17.306 3.68l2.6 5.274 4.52-3.76c5.84-3.97 13.593-2.32 17.308 3.68 3.718 6.003 1.998 14.088-3.842 18.064L109.74 57.02c-1.434 1.014-3.33.61-4.228-.9z',
            'fill-opacity': '.5'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'fill-opacity',
              'begin': '0.7s',
              'dur': '1.4s',
              'values': '0.5;1;0.5',
              'calcMode': 'linear',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('path', {
          attrs: {
            'd': 'M67.408 57.834l-23.01-24.98c-5.864-6.15-5.864-16.108 0-22.248 5.86-6.14 15.37-6.14 21.234 0L70 16.168l4.368-5.562c5.863-6.14 15.375-6.14 21.235 0 5.863 6.14 5.863 16.098 0 22.247l-23.007 24.98c-1.43 1.556-3.757 1.556-5.188 0z'
          }
        })
      ])
    }
  });

  var QSpinnerHourglass = Vue.extend({
    name: 'QSpinnerHourglass',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 100 100',
          'preserveAspectRatio': 'xMidYMid',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('g', [
          h('path', {
            staticClass: 'glass',
            attrs: {
              'fill': 'none',
              'stroke': 'currentColor',
              'stroke-width': '5',
              'stroke-miterlimit': '10',
              'd': 'M58.4,51.7c-0.9-0.9-1.4-2-1.4-2.3s0.5-0.4,1.4-1.4 C70.8,43.8,79.8,30.5,80,15.5H70H30H20c0.2,15,9.2,28.1,21.6,32.3c0.9,0.9,1.4,1.2,1.4,1.5s-0.5,1.6-1.4,2.5 C29.2,56.1,20.2,69.5,20,85.5h10h40h10C79.8,69.5,70.8,55.9,58.4,51.7z'
            }
          }),
          h('clipPath', {
            attrs: {
              'id': 'uil-hourglass-clip1'
            }
          }, [
            h('rect', {
              staticClass: 'clip',
              attrs: {
                'x': '15',
                'y': '20',
                'width': '70',
                'height': '25'
              }
            }, [
              h('animate', {
                attrs: {
                  'attributeName': 'height',
                  'from': '25',
                  'to': '0',
                  'dur': '1s',
                  'repeatCount': 'indefinite',
                  'values': '25;0;0',
                  'keyTimes': '0;0.5;1'
                }
              }),
              h('animate', {
                attrs: {
                  'attributeName': 'y',
                  'from': '20',
                  'to': '45',
                  'dur': '1s',
                  'repeatCount': 'indefinite',
                  'values': '20;45;45',
                  'keyTimes': '0;0.5;1'
                }
              })
            ])
          ]),
          h('clipPath', {
            attrs: {
              'id': 'uil-hourglass-clip2'
            }
          }, [
            h('rect', {
              staticClass: 'clip',
              attrs: {
                'x': '15',
                'y': '55',
                'width': '70',
                'height': '25'
              }
            }, [
              h('animate', {
                attrs: {
                  'attributeName': 'height',
                  'from': '0',
                  'to': '25',
                  'dur': '1s',
                  'repeatCount': 'indefinite',
                  'values': '0;25;25',
                  'keyTimes': '0;0.5;1'
                }
              }),
              h('animate', {
                attrs: {
                  'attributeName': 'y',
                  'from': '80',
                  'to': '55',
                  'dur': '1s',
                  'repeatCount': 'indefinite',
                  'values': '80;55;55',
                  'keyTimes': '0;0.5;1'
                }
              })
            ])
          ]),
          h('path', {
            staticClass: 'sand',
            attrs: {
              'd': 'M29,23c3.1,11.4,11.3,19.5,21,19.5S67.9,34.4,71,23H29z',
              'clip-path': 'url(#uil-hourglass-clip1)',
              'fill': 'currentColor'
            }
          }),
          h('path', {
            staticClass: 'sand',
            attrs: {
              'd': 'M71.6,78c-3-11.6-11.5-20-21.5-20s-18.5,8.4-21.5,20H71.6z',
              'clip-path': 'url(#uil-hourglass-clip2)',
              'fill': 'currentColor'
            }
          }),
          h('animateTransform', {
            attrs: {
              'attributeName': 'transform',
              'type': 'rotate',
              'from': '0 50 50',
              'to': '180 50 50',
              'repeatCount': 'indefinite',
              'dur': '1s',
              'values': '0 50 50;0 50 50;180 50 50',
              'keyTimes': '0;0.7;1'
            }
          })
        ])
      ])
    }
  });

  var QSpinnerInfinity = Vue.extend({
    name: 'QSpinnerInfinity',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 100 100',
          'preserveAspectRatio': 'xMidYMid'
        }
      }, [
        h('path', {
          attrs: {
            'd': 'M24.3,30C11.4,30,5,43.3,5,50s6.4,20,19.3,20c19.3,0,32.1-40,51.4-40C88.6,30,95,43.3,95,50s-6.4,20-19.3,20C56.4,70,43.6,30,24.3,30z',
            'fill': 'none',
            'stroke': 'currentColor',
            'stroke-width': '8',
            'stroke-dasharray': '10.691205342610678 10.691205342610678',
            'stroke-dashoffset': '0'
          }
        }, [
          h('animate', {
            attrs: {
              'attributeName': 'stroke-dashoffset',
              'from': '0',
              'to': '21.382410685221355',
              'begin': '0',
              'dur': '2s',
              'repeatCount': 'indefinite',
              'fill': 'freeze'
            }
          })
        ])
      ])
    }
  });

  var QSpinnerIos = Vue.extend({
    name: 'QSpinnerIos',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'stroke': 'currentColor',
          'fill': 'currentColor',
          'viewBox': '0 0 64 64'
        }
      }, [
        h('g', {
          attrs: {
            'stroke-width': '4',
            'stroke-linecap': 'round'
          }
        }, [
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(180)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '1;.85;.7;.65;.55;.45;.35;.25;.15;.1;0;1',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(210)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '0;1;.85;.7;.65;.55;.45;.35;.25;.15;.1;0',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(240)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '.1;0;1;.85;.7;.65;.55;.45;.35;.25;.15;.1',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(270)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '.15;.1;0;1;.85;.7;.65;.55;.45;.35;.25;.15',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(300)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '.25;.15;.1;0;1;.85;.7;.65;.55;.45;.35;.25',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(330)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '.35;.25;.15;.1;0;1;.85;.7;.65;.55;.45;.35',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(0)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '.45;.35;.25;.15;.1;0;1;.85;.7;.65;.55;.45',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(30)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '.55;.45;.35;.25;.15;.1;0;1;.85;.7;.65;.55',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(60)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '.65;.55;.45;.35;.25;.15;.1;0;1;.85;.7;.65',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(90)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '.7;.65;.55;.45;.35;.25;.15;.1;0;1;.85;.7',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(120)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '.85;.7;.65;.55;.45;.35;.25;.15;.1;0;1;.85',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('line', {
            attrs: {
              'y1': '17',
              'y2': '29',
              'transform': 'translate(32,32) rotate(150)'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'dur': '750ms',
                'values': '1;.85;.7;.65;.55;.45;.35;.25;.15;.1;0;1',
                'repeatCount': 'indefinite'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerOval = Vue.extend({
    name: 'QSpinnerOval',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'stroke': 'currentColor',
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 38 38',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('g', {
          attrs: {
            'transform': 'translate(1 1)',
            'stroke-width': '2',
            'fill': 'none',
            'fill-rule': 'evenodd'
          }
        }, [
          h('circle', {
            attrs: {
              'stroke-opacity': '.5',
              'cx': '18',
              'cy': '18',
              'r': '18'
            }
          }),
          h('path', {
            attrs: {
              'd': 'M36 18c0-9.94-8.06-18-18-18'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'rotate',
                'from': '0 18 18',
                'to': '360 18 18',
                'dur': '1s',
                'repeatCount': 'indefinite'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerPie = Vue.extend({
    name: 'QSpinnerPie',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 100 100',
          'preserveAspectRatio': 'xMidYMid',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('path', {
          attrs: {
            'd': 'M0 50A50 50 0 0 1 50 0L50 50L0 50',
            'fill': 'currentColor',
            'opacity': '0.5'
          }
        }, [
          h('animateTransform', {
            attrs: {
              'attributeName': 'transform',
              'type': 'rotate',
              'from': '0 50 50',
              'to': '360 50 50',
              'dur': '0.8s',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('path', {
          attrs: {
            'd': 'M50 0A50 50 0 0 1 100 50L50 50L50 0',
            'fill': 'currentColor',
            'opacity': '0.5'
          }
        }, [
          h('animateTransform', {
            attrs: {
              'attributeName': 'transform',
              'type': 'rotate',
              'from': '0 50 50',
              'to': '360 50 50',
              'dur': '1.6s',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('path', {
          attrs: {
            'd': 'M100 50A50 50 0 0 1 50 100L50 50L100 50',
            'fill': 'currentColor',
            'opacity': '0.5'
          }
        }, [
          h('animateTransform', {
            attrs: {
              'attributeName': 'transform',
              'type': 'rotate',
              'from': '0 50 50',
              'to': '360 50 50',
              'dur': '2.4s',
              'repeatCount': 'indefinite'
            }
          })
        ]),
        h('path', {
          attrs: {
            'd': 'M50 100A50 50 0 0 1 0 50L50 50L50 100',
            'fill': 'currentColor',
            'opacity': '0.5'
          }
        }, [
          h('animateTransform', {
            attrs: {
              'attributeName': 'transform',
              'type': 'rotate',
              'from': '0 50 50',
              'to': '360 50 50',
              'dur': '3.2s',
              'repeatCount': 'indefinite'
            }
          })
        ])
      ])
    }
  });

  var QSpinnerPuff = Vue.extend({
    name: 'QSpinnerPuff',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'stroke': 'currentColor',
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 44 44',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('g', {
          attrs: {
            'fill': 'none',
            'fill-rule': 'evenodd',
            'stroke-width': '2'
          }
        }, [
          h('circle', {
            attrs: {
              'cx': '22',
              'cy': '22',
              'r': '1'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'r',
                'begin': '0s',
                'dur': '1.8s',
                'values': '1; 20',
                'calcMode': 'spline',
                'keyTimes': '0; 1',
                'keySplines': '0.165, 0.84, 0.44, 1',
                'repeatCount': 'indefinite'
              }
            }),
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'begin': '0s',
                'dur': '1.8s',
                'values': '1; 0',
                'calcMode': 'spline',
                'keyTimes': '0; 1',
                'keySplines': '0.3, 0.61, 0.355, 1',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('circle', {
            attrs: {
              'cx': '22',
              'cy': '22',
              'r': '1'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'r',
                'begin': '-0.9s',
                'dur': '1.8s',
                'values': '1; 20',
                'calcMode': 'spline',
                'keyTimes': '0; 1',
                'keySplines': '0.165, 0.84, 0.44, 1',
                'repeatCount': 'indefinite'
              }
            }),
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'begin': '-0.9s',
                'dur': '1.8s',
                'values': '1; 0',
                'calcMode': 'spline',
                'keyTimes': '0; 1',
                'keySplines': '0.3, 0.61, 0.355, 1',
                'repeatCount': 'indefinite'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerRadio = Vue.extend({
    name: 'QSpinnerRadio',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 100 100',
          'preserveAspectRatio': 'xMidYMid',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('g', {
          attrs: {
            'transform': 'scale(0.55)'
          }
        }, [
          h('circle', {
            attrs: {
              'cx': '30',
              'cy': '150',
              'r': '30',
              'fill': 'currentColor'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'opacity',
                'from': '0',
                'to': '1',
                'dur': '1s',
                'begin': '0',
                'repeatCount': 'indefinite',
                'keyTimes': '0;0.5;1',
                'values': '0;1;1'
              }
            })
          ]),
          h('path', {
            attrs: {
              'd': 'M90,150h30c0-49.7-40.3-90-90-90v30C63.1,90,90,116.9,90,150z',
              'fill': 'currentColor'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'opacity',
                'from': '0',
                'to': '1',
                'dur': '1s',
                'begin': '0.1',
                'repeatCount': 'indefinite',
                'keyTimes': '0;0.5;1',
                'values': '0;1;1'
              }
            })
          ]),
          h('path', {
            attrs: {
              'd': 'M150,150h30C180,67.2,112.8,0,30,0v30C96.3,30,150,83.7,150,150z',
              'fill': 'currentColor'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'opacity',
                'from': '0',
                'to': '1',
                'dur': '1s',
                'begin': '0.2',
                'repeatCount': 'indefinite',
                'keyTimes': '0;0.5;1',
                'values': '0;1;1'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerRings = Vue.extend({
    name: 'QSpinnerRings',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'stroke': 'currentColor',
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 45 45',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('g', {
          attrs: {
            'fill': 'none',
            'fill-rule': 'evenodd',
            'transform': 'translate(1 1)',
            'stroke-width': '2'
          }
        }, [
          h('circle', {
            attrs: {
              'cx': '22',
              'cy': '22',
              'r': '6'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'r',
                'begin': '1.5s',
                'dur': '3s',
                'values': '6;22',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            }),
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'begin': '1.5s',
                'dur': '3s',
                'values': '1;0',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            }),
            h('animate', {
              attrs: {
                'attributeName': 'stroke-width',
                'begin': '1.5s',
                'dur': '3s',
                'values': '2;0',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('circle', {
            attrs: {
              'cx': '22',
              'cy': '22',
              'r': '6'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'r',
                'begin': '3s',
                'dur': '3s',
                'values': '6;22',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            }),
            h('animate', {
              attrs: {
                'attributeName': 'stroke-opacity',
                'begin': '3s',
                'dur': '3s',
                'values': '1;0',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            }),
            h('animate', {
              attrs: {
                'attributeName': 'stroke-width',
                'begin': '3s',
                'dur': '3s',
                'values': '2;0',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('circle', {
            attrs: {
              'cx': '22',
              'cy': '22',
              'r': '8'
            }
          }, [
            h('animate', {
              attrs: {
                'attributeName': 'r',
                'begin': '0s',
                'dur': '1.5s',
                'values': '6;1;2;3;4;5;6',
                'calcMode': 'linear',
                'repeatCount': 'indefinite'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSpinnerTail = Vue.extend({
    name: 'QSpinnerTail',

    mixins: [mixin],

    render: function render (h) {
      return h('svg', {
        staticClass: 'q-spinner',
        class: this.classes,
        on: this.$listeners,
        attrs: {
          focusable: 'false' /* needed for IE11 */,
          'width': this.cSize,
          'height': this.cSize,
          'viewBox': '0 0 38 38',
          'xmlns': 'http://www.w3.org/2000/svg'
        }
      }, [
        h('defs', [
          h('linearGradient', {
            attrs: {
              'x1': '8.042%',
              'y1': '0%',
              'x2': '65.682%',
              'y2': '23.865%',
              'id': 'a'
            }
          }, [
            h('stop', {
              attrs: {
                'stop-color': 'currentColor',
                'stop-opacity': '0',
                'offset': '0%'
              }
            }),
            h('stop', {
              attrs: {
                'stop-color': 'currentColor',
                'stop-opacity': '.631',
                'offset': '63.146%'
              }
            }),
            h('stop', {
              attrs: {
                'stop-color': 'currentColor',
                'offset': '100%'
              }
            })
          ])
        ]),
        h('g', {
          attrs: {
            'transform': 'translate(1 1)',
            'fill': 'none',
            'fill-rule': 'evenodd'
          }
        }, [
          h('path', {
            attrs: {
              'd': 'M36 18c0-9.94-8.06-18-18-18',
              'stroke': 'url(#a)',
              'stroke-width': '2'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'rotate',
                'from': '0 18 18',
                'to': '360 18 18',
                'dur': '0.9s',
                'repeatCount': 'indefinite'
              }
            })
          ]),
          h('circle', {
            attrs: {
              'fill': 'currentColor',
              'cx': '36',
              'cy': '18',
              'r': '1'
            }
          }, [
            h('animateTransform', {
              attrs: {
                'attributeName': 'transform',
                'type': 'rotate',
                'from': '0 18 18',
                'to': '360 18 18',
                'dur': '0.9s',
                'repeatCount': 'indefinite'
              }
            })
          ])
        ])
      ])
    }
  });

  var QSplitter = Vue.extend({
    name: 'QSplitter',

    mixins: [ DarkMixin ],

    directives: {
      TouchPan: TouchPan
    },

    props: {
      value: {
        type: Number,
        required: true
      },
      reverse: Boolean,
      unit: {
        type: String,
        default: '%',
        validator: function (v) { return [ '%', 'px' ].includes(v); }
      },

      limits: {
        type: Array,
        validator: function (v) {
          if (v.length !== 2) { return false }
          if (typeof v[0] !== 'number' || typeof v[1] !== 'number') { return false }
          return v[0] >= 0 && v[0] <= v[1]
        }
      },

      emitImmediately: Boolean,

      horizontal: Boolean,
      disable: Boolean,

      beforeClass: [Array, String, Object],
      afterClass: [Array, String, Object],

      separatorClass: [Array, String, Object],
      separatorStyle: [Array, String, Object]
    },

    watch: {
      value: {
        immediate: true,
        handler: function handler (v) {
          this.__normalize(v, this.computedLimits);
        }
      },

      limits: {
        deep: true,
        handler: function handler () {
          var this$1 = this;

          this.$nextTick(function () {
            this$1.__normalize(this$1.value, this$1.computedLimits);
          });
        }
      }
    },

    computed: {
      classes: function classes () {
        return (this.horizontal === true ? 'column' : 'row') +
          " q-splitter--" + (this.horizontal === true ? 'horizontal' : 'vertical') +
          " q-splitter--" + (this.disable === true ? 'disabled' : 'workable') +
          (this.isDark === true ? ' q-splitter--dark' : '')
      },

      prop: function prop () {
        return this.horizontal === true ? 'height' : 'width'
      },

      side: function side () {
        return this.reverse !== true ? 'before' : 'after'
      },

      computedLimits: function computedLimits () {
        return this.limits !== void 0
          ? this.limits
          : (this.unit === '%' ? [ 10, 90 ] : [ 50, Infinity ])
      },

      styles: function styles () {
        var obj, obj$1;

        return ( obj$1 = {}, obj$1[this.side] = ( obj = {}, obj[this.prop] = this.__getCSSValue(this.value), obj ), obj$1 )
      }
    },

    methods: {
      __pan: function __pan (evt) {
        if (evt.isFirst === true) {
          var size = this.$el.getBoundingClientRect()[this.prop];

          this.__dir = this.horizontal === true ? 'up' : 'left';
          this.__maxValue = this.unit === '%' ? 100 : size;
          this.__value = Math.min(this.__maxValue, this.computedLimits[1], Math.max(this.computedLimits[0], this.value));
          this.__multiplier = (this.reverse !== true ? 1 : -1) *
            (this.horizontal === true ? 1 : (this.$q.lang.rtl === true ? -1 : 1)) *
            (this.unit === '%' ? (size === 0 ? 0 : 100 / size) : 1);

          this.$el.classList.add('q-splitter--active');
          return
        }

        if (evt.isFinal === true) {
          if (this.__normalized !== this.value) {
            this.$emit('input', this.__normalized);
          }

          this.$el.classList.remove('q-splitter--active');
          return
        }

        var val = this.__value +
          this.__multiplier *
          (evt.direction === this.__dir ? -1 : 1) *
          evt.distance[this.horizontal === true ? 'y' : 'x'];

        this.__normalized = Math.min(this.__maxValue, this.computedLimits[1], Math.max(this.computedLimits[0], val));

        this.$refs[this.side].style[this.prop] = this.__getCSSValue(this.__normalized);

        if (this.emitImmediately === true && this.value !== this.__normalized) {
          this.$emit('input', this.__normalized);
        }
      },

      __normalize: function __normalize (val, limits) {
        if (val < limits[0]) {
          this.$emit('input', limits[0]);
        }
        else if (val > limits[1]) {
          this.$emit('input', limits[1]);
        }
      },

      __getCSSValue: function __getCSSValue (value) {
        return (this.unit === '%' ? value : Math.round(value)) + this.unit
      }
    },

    render: function render (h) {
      var child = [
        h('div', {
          ref: 'before',
          staticClass: 'q-splitter__panel q-splitter__before' + (this.reverse === true ? ' col' : ''),
          style: this.styles.before,
          class: this.beforeClass,
          on: cache(this, 'stop', { input: stop })
        }, slot(this, 'before')),

        h('div', {
          staticClass: 'q-splitter__separator',
          style: this.separatorStyle,
          class: this.separatorClass
        }, [
          h('div', {
            staticClass: 'absolute-full q-splitter__separator-area',
            directives: this.disable === true ? void 0 : cache(this, 'dir#' + this.horizontal, [{
              name: 'touch-pan',
              value: this.__pan,
              modifiers: {
                horizontal: this.horizontal !== true,
                vertical: this.horizontal,
                prevent: true,
                stop: true,
                mouse: true,
                mouseAllDir: true
              }
            }])
          }, slot(this, 'separator'))
        ]),

        h('div', {
          ref: 'after',
          staticClass: 'q-splitter__panel q-splitter__after' + (this.reverse === true ? '' : ' col'),
          style: this.styles.after,
          class: this.afterClass,
          on: cache(this, 'stop', { input: stop })
        }, slot(this, 'after'))
      ];

      return h('div', {
        staticClass: 'q-splitter no-wrap',
        class: this.classes,
        on: this.$listeners
      }, mergeSlot(child, this, 'default'))
    }
  });

  var StepHeader = Vue.extend({
    name: 'StepHeader',

    directives: {
      Ripple: Ripple
    },

    props: {
      stepper: {},
      step: {}
    },

    computed: {
      isActive: function isActive () {
        return this.stepper.value === this.step.name
      },

      isDisable: function isDisable () {
        var opt = this.step.disable;
        return opt === true || opt === ''
      },

      isError: function isError () {
        var opt = this.step.error;
        return opt === true || opt === ''
      },

      isDone: function isDone () {
        var opt = this.step.done;
        return !this.isDisable && (opt === true || opt === '')
      },

      headerNav: function headerNav () {
        var
          opt = this.step.headerNav,
          nav = opt === true || opt === '' || opt === void 0;

        return !this.isDisable && this.stepper.headerNav && (this.isActive || nav)
      },

      hasPrefix: function hasPrefix () {
        return this.step.prefix && !this.isActive && !this.isError && !this.isDone
      },

      icon: function icon () {
        if (this.isActive) {
          return this.step.activeIcon || this.stepper.activeIcon || this.$q.iconSet.stepper.active
        }
        if (this.isError) {
          return this.step.errorIcon || this.stepper.errorIcon || this.$q.iconSet.stepper.error
        }
        if (!this.isDisable && this.isDone) {
          return this.step.doneIcon || this.stepper.doneIcon || this.$q.iconSet.stepper.done
        }

        return this.step.icon || this.stepper.inactiveIcon
      },

      color: function color () {
        if (this.isActive) {
          return this.step.activeColor || this.stepper.activeColor || this.step.color
        }
        if (this.isError) {
          return this.step.errorColor || this.stepper.errorColor
        }
        if (!this.disable && this.isDone) {
          return this.step.doneColor || this.stepper.doneColor || this.step.color || this.stepper.inactiveColor
        }

        return this.step.color || this.stepper.inactiveColor
      },

      classes: function classes () {
        var obj;

        return ( obj = {}, obj[("text-" + (this.color))] = this.color, obj['q-stepper__tab--error'] = this.isError, obj['q-stepper__tab--active'] = this.isActive, obj['q-stepper__tab--done'] = this.isDone, obj['q-stepper__tab--navigation q-focusable q-hoverable'] = this.headerNav, obj['q-stepper__tab--disabled'] = this.isDisable, obj )
      }
    },

    methods: {
      activate: function activate () {
        this.$refs.blurTarget !== void 0 && this.$refs.blurTarget.focus();
        !this.isActive && this.stepper.goTo(this.step.name);
      },
      keyup: function keyup (e) {
        e.keyCode === 13 && !this.isActive && this.stepper.goTo(this.step.name);
      }
    },

    render: function render (h) {
      var data = {
        staticClass: 'q-stepper__tab col-grow flex items-center no-wrap relative-position',
        class: this.classes,
        directives: this.stepper.headerNav ? [{
          name: 'ripple',
          value: this.headerNav
        }] : null
      };

      if (this.headerNav) {
        data.on = {
          click: this.activate,
          keyup: this.keyup
        };
        data.attrs = { tabindex: this.isDisable === true ? -1 : this.$attrs.tabindex || 0 };
      }

      return h('div', data, [
        h('div', { staticClass: 'q-focus-helper', attrs: { tabindex: -1 }, ref: 'blurTarget' }),

        h('div', { staticClass: 'q-stepper__dot row flex-center q-stepper__line relative-position' }, [
          h('span', { staticClass: 'row flex-center' }, [
            this.hasPrefix === true
              ? this.step.prefix
              : h(QIcon, { props: { name: this.icon } })
          ])
        ]),

        this.step.title
          ? h('div', {
            staticClass: 'q-stepper__label q-stepper__line relative-position'
          }, [
            h('div', { staticClass: 'q-stepper__title' }, [ this.step.title ]),
            this.step.caption
              ? h('div', { staticClass: 'q-stepper__caption' }, [ this.step.caption ])
              : null
          ])
          : null
      ])
    }
  });

  var StepWrapper = Vue.extend({
    name: 'QStepWrapper',

    render: function render (h) {
      return h('div', {
        staticClass: 'q-stepper__step-content'
      }, [
        h('div', {
          staticClass: 'q-stepper__step-inner'
        }, slot(this, 'default'))
      ])
    }
  });

  var QStep = Vue.extend({
    name: 'QStep',

    inject: {
      stepper: {
        default: function default$1 () {
          console.error('QStep needs to be child of QStepper');
        }
      }
    },

    mixins: [ PanelChildMixin ],

    props: {
      icon: String,
      color: String,
      title: {
        type: String,
        required: true
      },
      caption: String,
      prefix: [ String, Number ],

      doneIcon: String,
      doneColor: String,
      activeIcon: String,
      activeColor: String,
      errorIcon: String,
      errorColor: String,

      headerNav: {
        type: Boolean,
        default: true
      },
      done: Boolean,
      error: Boolean
    },

    computed: {
      isActive: function isActive () {
        return this.stepper.value === this.name
      }
    },

    watch: {
      isActive: function isActive (active) {
        var this$1 = this;

        if (
          active === true &&
          this.stepper.vertical === true
        ) {
          this.$nextTick(function () {
            if (this$1.$el !== void 0) {
              this$1.$el.scrollTop = 0;
            }
          });
        }
      }
    },

    render: function render (h) {
      var vertical = this.stepper.vertical;
      var content = vertical === true && this.stepper.keepAlive === true
        ? h(
          'keep-alive',
          this.isActive === true
            ? [ h(StepWrapper, { key: this.name }, slot(this, 'default')) ]
            : void 0
        )
        : (
          vertical !== true || this.isActive === true
            ? StepWrapper.options.render.call(this, h)
            : void 0
        );

      return h(
        'div',
        {
          staticClass: 'q-stepper__step',
          on: this.$listeners
        },
        vertical === true
          ? [
            h(StepHeader, {
              props: {
                stepper: this.stepper,
                step: this
              }
            }),

            this.stepper.animated === true
              ? h(QSlideTransition, [ content ])
              : content
          ]
          : [ content ]
      )
    }
  });

  var QStepper = Vue.extend({
    name: 'QStepper',

    provide: function provide () {
      return {
        stepper: this
      }
    },

    mixins: [ DarkMixin, PanelParentMixin ],

    props: {
      flat: Boolean,
      bordered: Boolean,
      alternativeLabels: Boolean,
      headerNav: Boolean,
      contracted: Boolean,

      inactiveColor: String,
      inactiveIcon: String,
      doneIcon: String,
      doneColor: String,
      activeIcon: String,
      activeColor: String,
      errorIcon: String,
      errorColor: String
    },

    computed: {
      classes: function classes () {
        return "q-stepper--" + (this.vertical === true ? 'vertical' : 'horizontal') +
          (this.flat === true || this.isDark === true ? ' q-stepper--flat no-shadow' : '') +
          (this.bordered === true || (this.isDark === true && this.flat === false) ? ' q-stepper--bordered' : '') +
          (this.contracted === true ? ' q-stepper--contracted' : '') +
          (this.isDark === true ? ' q-stepper--dark q-dark' : '')
      }
    },

    methods: {
      __getContent: function __getContent (h) {
        var this$1 = this;
        var obj;

        var top = slot(this, 'message', []);

        if (this.vertical === true) {
          this.__isValidPanelName(this.value) && this.__updatePanelIndex();

          return top.concat(
            h('div', {
              staticClass: 'q-stepper__content',
              // stop propagation of content emitted @input
              // which would tamper with Panel's model
              on: cache(this, 'stop', { input: stop })
            }, slot(this, 'default'))
          )
        }

        return [
          h('div', {
            staticClass: 'q-stepper__header row items-stretch justify-between',
            class: ( obj = {}, obj[("q-stepper__header--" + (this.alternativeLabels ? 'alternative' : 'standard') + "-labels")] = true, obj['q-stepper__header--border'] = !this.flat || this.bordered, obj )
          }, this.__getAllPanels().map(function (panel) {
            var step = panel.componentOptions.propsData;

            return h(StepHeader, {
              key: step.name,
              props: {
                stepper: this$1,
                step: step
              }
            })
          }))
        ].concat(
          top,

          h('div', {
            staticClass: 'q-stepper__content q-panel-parent',
            directives: this.panelDirectives
          }, this.__getPanelContent(h))
        )
      },

      __renderPanels: function __renderPanels (h) {
        return h('div', {
          staticClass: 'q-stepper',
          class: this.classes,
          on: this.$listeners
        }, mergeSlot(this.__getContent(h), this, 'navigation'))
      }
    }
  });

  var QStepperNavigation = Vue.extend({
    name: 'QStepperNavigation',

    render: function render (h) {
      return h('div', {
        staticClass: 'q-stepper__nav',
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var Top = {
    computed: {
      marginalsProps: function marginalsProps () {
        return {
          pagination: this.computedPagination,
          pagesNumber: this.pagesNumber,
          isFirstPage: this.isFirstPage,
          isLastPage: this.isLastPage,
          prevPage: this.prevPage,
          nextPage: this.nextPage,

          inFullscreen: this.inFullscreen,
          toggleFullscreen: this.toggleFullscreen
        }
      }
    },

    methods: {
      getTop: function getTop (h) {
        var
          top = this.$scopedSlots.top,
          topLeft = this.$scopedSlots['top-left'],
          topRight = this.$scopedSlots['top-right'],
          topSelection = this.$scopedSlots['top-selection'],
          hasSelection = this.hasSelectionMode === true &&
            topSelection !== void 0 &&
            this.rowsSelectedNumber > 0,
          staticClass = 'q-table__top relative-position row items-center';

        if (top !== void 0) {
          return h('div', { staticClass: staticClass }, [ top(this.marginalsProps) ])
        }

        var child;

        if (hasSelection === true) {
          child = topSelection(this.marginalsProps).slice();
        }
        else {
          child = [];

          if (topLeft !== void 0) {
            child.push(
              h('div', { staticClass: 'q-table-control' }, [
                topLeft(this.marginalsProps)
              ])
            );
          }
          else if (this.title) {
            child.push(
              h('div', { staticClass: 'q-table__control' }, [
                h('div', { staticClass: 'q-table__title' }, this.title)
              ])
            );
          }
        }

        if (topRight !== void 0) {
          child.push(h('div', { staticClass: 'q-table__separator col' }));
          child.push(
            h('div', { staticClass: 'q-table__control' }, [
              topRight(this.marginalsProps)
            ])
          );
        }

        if (child.length === 0) {
          return
        }

        return h('div', { staticClass: staticClass }, child)
      }
    }
  };

  var QTh = Vue.extend({
    name: 'QTh',

    props: {
      props: Object,
      autoWidth: Boolean
    },

    render: function render (h) {
      var this$1 = this;

      var on = this.$listeners;

      if (this.props === void 0) {
        return h('th', {
          on: on,
          class: this.autoWidth === true ? 'q-table--col-auto-width' : null
        }, slot(this, 'default'))
      }

      var col, child;
      var name = this.$vnode.key;

      if (name) {
        col = this.props.colsMap[name];
        if (col === void 0) { return }
      }
      else {
        col = this.props.col;
      }

      if (col.sortable === true) {
        var action = col.align === 'right'
          ? 'unshift'
          : 'push';

        child = uniqueSlot(this, 'default', []);
        child[action](
          h(QIcon, {
            props: { name: this.$q.iconSet.table.arrowUp },
            staticClass: col.__iconClass
          })
        );
      }
      else {
        child = slot(this, 'default');
      }

      var evt = col.sortable === true
        ? {
          click: function (evt) {
            this$1.props.sort(col);
            this$1.$emit('click', evt);
          }
        }
        : {};

      return h('th', {
        on: Object.assign({}, on, evt),
        style: col.__thStyle,
        class: col.__thClass +
          (this.autoWidth === true ? ' q-table--col-auto-width' : '')
      }, child)
    }
  });

  var TableHeader = {
    methods: {
      getTableHeader: function getTableHeader (h) {
        var child = this.getTableHeaderRow(h);

        if (this.loading === true && this.$scopedSlots.loading === void 0) {
          child.push(
            h('tr', { staticClass: 'q-table__progress' }, [
              h('th', {
                staticClass: 'relative-position',
                attrs: { colspan: '100%' }
              }, this.__getProgress(h))
            ])
          );
        }

        return h('thead', child)
      },

      getTableHeaderRow: function getTableHeaderRow (h) {
        var this$1 = this;

        var
          header = this.$scopedSlots.header,
          headerCell = this.$scopedSlots['header-cell'];

        if (header !== void 0) {
          return header(this.addTableHeaderRowMeta({
            header: true, cols: this.computedCols, sort: this.sort, colsMap: this.computedColsMap
          })).slice()
        }

        var mapFn;

        if (headerCell !== void 0) {
          mapFn = function (col) { return headerCell({
            col: col, cols: this$1.computedCols, sort: this$1.sort, colsMap: this$1.computedColsMap
          }); };
        }
        else {
          mapFn = function (col) {
            var props = {
              col: col, cols: this$1.computedCols, sort: this$1.sort, colsMap: this$1.computedColsMap
            };
            var slot = this$1.$scopedSlots[("header-cell-" + (col.name))];

            return slot !== void 0
              ? slot(props)
              : h(QTh, {
                key: col.name,
                props: { props: props },
                style: col.headerStyle,
                class: col.headerClasses
              }, col.label)
          };
        }

        var child = this.computedCols.map(mapFn);

        if (this.singleSelection === true && this.grid !== true) {
          child.unshift(h('th', { staticClass: 'q-table--col-auto-width' }, [' ']));
        }
        else if (this.multipleSelection === true) {
          child.unshift(h('th', { staticClass: 'q-table--col-auto-width' }, [
            h(QCheckbox, {
              props: {
                color: this.color,
                value: this.someRowsSelected === true
                  ? null
                  : this.allRowsSelected,
                dark: this.isDark,
                dense: this.dense
              },
              on: cache(this, 'inp', {
                input: function (val) {
                  if (this$1.someRowsSelected === true) {
                    val = false;
                  }
                  this$1.__updateSelection(
                    this$1.computedRows.map(this$1.getRowKey),
                    this$1.computedRows,
                    val
                  );
                }
              })
            })
          ]));
        }

        return [
          h('tr', {
            style: this.tableHeaderStyle,
            class: this.tableHeaderClass
          }, child)
        ]
      },

      addTableHeaderRowMeta: function addTableHeaderRowMeta (data) {
        var this$1 = this;

        if (this.multipleSelection === true) {
          Object.defineProperty(data, 'selected', {
            get: function () { return this$1.someRowsSelected === true
              ? 'some'
              : this$1.allRowsSelected; },
            set: function (val) {
              if (this$1.someRowsSelected === true) {
                val = false;
              }
              this$1.__updateSelection(
                this$1.computedRows.map(this$1.getRowKey),
                this$1.computedRows,
                val
              );
            },
            configurable: true,
            enumerable: true
          });
          data.partialSelected = this.someRowsSelected;
          data.multipleSelect = true;
        }

        return data
      }
    }
  };

  var TableBody = {
    methods: {
      getTableRowBody: function getTableRowBody (row, body) {
        var
          key = this.getRowKey(row),
          selected = this.isRowSelected(key);

        return body(this.addBodyRowMeta({
          key: key,
          row: row,
          cols: this.computedCols,
          colsMap: this.computedColsMap,
          __trClass: selected ? 'selected' : ''
        }))
      },

      getTableRow: function getTableRow (h, row) {
        var this$1 = this;

        var
          bodyCell = this.$scopedSlots['body-cell'],
          key = this.getRowKey(row),
          selected = this.isRowSelected(key),
          child = bodyCell
            ? this.computedCols.map(function (col) { return bodyCell(this$1.addBodyCellMetaData({ row: row, col: col })); })
            : this.computedCols.map(function (col) {
              var slot = this$1.$scopedSlots[("body-cell-" + (col.name))];
              return slot !== void 0
                ? slot(this$1.addBodyCellMetaData({ row: row, col: col }))
                : h('td', {
                  class: col.__tdClass,
                  style: col.__tdStyle
                }, this$1.getCellValue(col, row))
            });

        this.hasSelectionMode === true && child.unshift(
          h('td', { staticClass: 'q-table--col-auto-width' }, [
            h(QCheckbox, {
              props: {
                value: selected,
                color: this.color,
                dark: this.isDark,
                dense: this.dense
              },
              on: {
                input: function (adding) {
                  this$1.__updateSelection([ key ], [ row ], adding);
                }
              }
            })
          ])
        );

        var data = { key: key, class: { selected: selected }, on: {} };

        if (this.$listeners['row-click'] !== void 0) {
          data.class['cursor-pointer'] = true;
          data.on.click = function (evt) {
            this$1.$emit('row-click', evt, row);
          };
        }

        if (this.$listeners['row-dblclick'] !== void 0) {
          data.class['cursor-pointer'] = true;
          data.on.dblclick = function (evt) {
            this$1.$emit('row-dblclick', evt, row);
          };
        }

        return h('tr', data, child)
      },

      getTableBody: function getTableBody (h) {
        var this$1 = this;

        var
          body = this.$scopedSlots.body,
          topRow = this.$scopedSlots['top-row'],
          bottomRow = this.$scopedSlots['bottom-row'],
          mapFn = body !== void 0
            ? function (row) { return this$1.getTableRowBody(row, body); }
            : function (row) { return this$1.getTableRow(h, row); };

        var child = this.computedRows.map(mapFn);

        if (topRow !== void 0) {
          child = topRow({ cols: this.computedCols }).concat(child);
        }
        if (bottomRow !== void 0) {
          child = child.concat(bottomRow({ cols: this.computedCols }));
        }

        return h('tbody', child)
      },

      getTableRowVirtual: function getTableRowVirtual (h) {
        var this$1 = this;

        var body = this.$scopedSlots.body;

        return body !== void 0
          ? function (props) { return this$1.getTableRowBody(props.item, body); }
          : function (props) { return this$1.getTableRow(h, props.item); }
      },

      addBodyRowMeta: function addBodyRowMeta (data) {
        var this$1 = this;

        this.hasSelectionMode === true && Object.defineProperty(data, 'selected', {
          get: function () { return this$1.isRowSelected(data.key); },
          set: function (adding) {
            this$1.__updateSelection([ data.key ], [ data.row ], adding);
          },
          configurable: true,
          enumerable: true
        });

        Object.defineProperty(data, 'expand', {
          get: function () { return this$1.isRowExpanded(data.key); },
          set: function (adding) {
            this$1.__updateExpanded(data.key, adding);
          },
          configurable: true,
          enumerable: true
        });

        data.cols = data.cols.map(function (col) {
          var c = Object.assign({}, col);
          Object.defineProperty(c, 'value', {
            get: function () { return this$1.getCellValue(col, data.row); },
            configurable: true,
            enumerable: true
          });
          return c
        });

        return data
      },

      addBodyCellMetaData: function addBodyCellMetaData (data) {
        var this$1 = this;

        Object.defineProperty(data, 'value', {
          get: function () { return this$1.getCellValue(data.col, data.row); },
          configurable: true,
          enumerable: true
        });
        return data
      },

      getCellValue: function getCellValue (col, row) {
        var val = typeof col.field === 'function' ? col.field(row) : row[col.field];
        return col.format !== void 0 ? col.format(val, row) : val
      }
    }
  };

  var Bottom = {
    computed: {
      navIcon: function navIcon () {
        var ico = [ this.$q.iconSet.table.prevPage, this.$q.iconSet.table.nextPage ];
        return this.$q.lang.rtl === true ? ico.reverse() : ico
      }
    },

    methods: {
      getBottom: function getBottom (h) {
        if (this.hideBottom === true) {
          return
        }

        if (this.nothingToDisplay === true) {
          var message = this.loading === true
            ? this.loadingLabel || this.$q.lang.table.loading
            : (this.filter ? this.noResultsLabel || this.$q.lang.table.noResults : this.noDataLabel || this.$q.lang.table.noData);

          var noData = this.$scopedSlots['no-data'];
          var children = noData !== void 0
            ? [ noData({ message: message, icon: this.$q.iconSet.table.warning, filter: this.filter }) ]
            : [
              h(QIcon, {
                staticClass: 'q-table__bottom-nodata-icon',
                props: { name: this.$q.iconSet.table.warning }
              }),
              message
            ];

          return h('div', {
            staticClass: 'q-table__bottom row items-center q-table__bottom--nodata'
          }, children)
        }

        var bottom = this.$scopedSlots.bottom;

        return h('div', {
          staticClass: 'q-table__bottom row items-center',
          class: bottom !== void 0 ? null : 'justify-end'
        }, bottom !== void 0 ? [ bottom(this.marginalsProps) ] : this.getPaginationRow(h))
      },

      getPaginationRow: function getPaginationRow (h) {
        var this$1 = this;

        var control;
        var ref = this.computedPagination;
        var rowsPerPage = ref.rowsPerPage;
        var paginationLabel = this.paginationLabel || this.$q.lang.table.pagination,
          paginationSlot = this.$scopedSlots.pagination,
          hasOpts = this.rowsPerPageOptions.length > 1;

        var child = [
          h('div', { staticClass: 'q-table__control' }, [
            h('div', [
              this.hasSelectionMode === true && this.rowsSelectedNumber > 0
                ? (this.selectedRowsLabel || this.$q.lang.table.selectedRecords)(this.rowsSelectedNumber)
                : ''
            ])
          ]),

          h('div', { staticClass: 'q-table__separator col' })
        ];

        if (hasOpts === true) {
          child.push(
            h('div', { staticClass: 'q-table__control' }, [
              h('span', { staticClass: 'q-table__bottom-item' }, [
                this.rowsPerPageLabel || this.$q.lang.table.recordsPerPage
              ]),
              h(QSelect, {
                staticClass: 'q-table__select inline q-table__bottom-item',
                props: {
                  color: this.color,
                  value: rowsPerPage,
                  options: this.computedRowsPerPageOptions,
                  displayValue: rowsPerPage === 0
                    ? this.$q.lang.table.allRows
                    : rowsPerPage,
                  dark: this.isDark,
                  borderless: true,
                  dense: true,
                  optionsDense: true,
                  optionsCover: true
                },
                on: cache(this, 'pgSize', {
                  input: function (pag) {
                    this$1.setPagination({
                      page: 1,
                      rowsPerPage: pag.value
                    });
                  }
                })
              })
            ])
          );
        }

        if (paginationSlot !== void 0) {
          control = paginationSlot(this.marginalsProps);
        }
        else {
          control = [
            h('span', rowsPerPage !== 0 ? { staticClass: 'q-table__bottom-item' } : {}, [
              rowsPerPage
                ? paginationLabel(this.firstRowIndex + 1, Math.min(this.lastRowIndex, this.computedRowsNumber), this.computedRowsNumber)
                : paginationLabel(1, this.computedData.rowsNumber, this.computedRowsNumber)
            ])
          ];

          if (rowsPerPage !== 0) {
            var size = this.dense === true ? 'sm' : void 0;

            control.push(
              h(QBtn, {
                props: {
                  color: this.color,
                  round: true,
                  icon: this.navIcon[0],
                  dense: true,
                  flat: true,
                  size: size,
                  disable: this.isFirstPage
                },
                on: cache(this, 'pgPrev', { click: this.prevPage })
              }),

              h(QBtn, {
                props: {
                  color: this.color,
                  round: true,
                  icon: this.navIcon[1],
                  dense: true,
                  size: size,
                  flat: true,
                  disable: this.isLastPage
                },
                on: cache(this, 'pgNext', { click: this.nextPage })
              })
            );
          }
        }

        child.push(
          h('div', { staticClass: 'q-table__control' }, control)
        );

        return child
      }
    }
  };

  var TableGrid = {
    methods: {
      getGridBody: function getGridBody (h) {
        var this$1 = this;

        var item = this.$scopedSlots.item !== void 0
          ? this.$scopedSlots.item
          : function (scope) {
            var child = scope.cols.map(
              function (col) { return h('div', { staticClass: 'q-table__grid-item-row' }, [
                h('div', { staticClass: 'q-table__grid-item-title' }, [ col.label ]),
                h('div', { staticClass: 'q-table__grid-item-value' }, [ col.value ])
              ]); }
            );

            this$1.hasSelectionMode === true && child.unshift(
              h('div', { staticClass: 'q-table__grid-item-row' }, [
                h(QCheckbox, {
                  props: {
                    value: scope.selected,
                    color: this$1.color,
                    dark: this$1.isDark,
                    dense: true
                  },
                  on: {
                    input: function (val) {
                      scope.selected = val;
                    }
                  }
                })
              ]),

              h(QSeparator, { props: { dark: this$1.isDark } })
            );

            var data = {
              staticClass: 'q-table__grid-item-card' + this$1.cardDefaultClass,
              class: this$1.cardClass,
              style: this$1.cardStyle,
              on: {}
            };

            if (this$1.$listeners['row-click'] !== void 0 || this$1.$listeners['row-dblclick'] !== void 0) {
              data.staticClass += ' cursor-pointer';
            }

            if (this$1.$listeners['row-click'] !== void 0) {
              data.on.click = function (evt) {
                this$1.$emit('row-click', evt, scope.row);
              };
            }

            if (this$1.$listeners['row-dblclick'] !== void 0) {
              data.on.dblclick = function (evt) {
                this$1.$emit('row-dblclick', evt, scope.row);
              };
            }

            return h('div', {
              staticClass: 'q-table__grid-item col-xs-12 col-sm-6 col-md-4 col-lg-3',
              class: scope.selected === true ? 'q-table__grid-item--selected' : ''
            }, [
              h('div', data, child)
            ])
          };

        return h('div', {
          staticClass: 'q-table__grid-content row',
          class: this.cardContainerClass,
          style: this.cardContainerStyle
        }, this.computedRows.map(function (row) {
          var
            key = this$1.getRowKey(row),
            selected = this$1.isRowSelected(key);

          return item(this$1.addBodyRowMeta({
            key: key,
            row: row,
            cols: this$1.computedCols,
            colsMap: this$1.computedColsMap,
            __trClass: selected ? 'selected' : ''
          }))
        }))
      },

      getGridHeader: function getGridHeader (h) {
        var child = this.gridHeader === true
          ? [
            h('table', { staticClass: 'q-table' }, [
              this.getTableHeader(h)
            ])
          ]
          : (
            this.loading === true && this.$scopedSlots.loading === void 0
              ? this.__getProgress(h)
              : void 0
          );

        return h('div', { staticClass: 'q-table__middle' }, child)
      }
    }
  };

  function getTableMiddle (h, conf, content) {
    return h('div', Object.assign({}, conf,
      {staticClass: 'q-table__middle' + (conf.staticClass !== void 0 ? ' ' + conf.staticClass : '')}), [
      h('table', { staticClass: 'q-table' }, content)
    ])
  }

  var comps = {
    list: QList,
    table: QMarkupTable
  };

  var QVirtualScroll = Vue.extend({
    name: 'QVirtualScroll',

    mixins: [ VirtualScroll ],

    props: {
      type: {
        type: String,
        default: 'list',
        validator: function (v) { return ['list', 'table', '__qtable'].includes(v); }
      },

      items: {
        type: Array,
        default: function () { return []; }
      },

      itemsFn: Function,
      itemsSize: Number,

      scrollTarget: {
        default: void 0
      }
    },

    computed: {
      virtualScrollLength: function virtualScrollLength () {
        return this.itemsSize >= 0 && this.itemsFn !== void 0
          ? parseInt(this.itemsSize, 10)
          : (Array.isArray(this.items) ? this.items.length : 0)
      },

      virtualScrollScope: function virtualScrollScope () {
        var this$1 = this;

        if (this.virtualScrollLength === 0) {
          return []
        }

        var mapFn = function (item, i) { return ({
          index: this$1.virtualScrollSliceRange.from + i,
          item: item
        }); };

        if (this.itemsFn === void 0) {
          return this.items.slice(this.virtualScrollSliceRange.from, this.virtualScrollSliceRange.to).map(mapFn)
        }

        return this.itemsFn(this.virtualScrollSliceRange.from, this.virtualScrollSliceRange.to - this.virtualScrollSliceRange.from).map(mapFn)
      },

      classes: function classes () {
        return 'q-virtual-scroll q-virtual-scroll' + (this.virtualScrollHorizontal === true ? '--horizontal' : '--vertical') +
          (this.scrollTarget !== void 0 ? '' : ' scroll')
      },

      attrs: function attrs () {
        return this.scrollTarget !== void 0 ? void 0 : { tabindex: 0 }
      }
    },

    watch: {
      virtualScrollLength: function virtualScrollLength () {
        this.__resetVirtualScroll();
      },

      scrollTarget: function scrollTarget () {
        this.__unconfigureScrollTarget();
        this.__configureScrollTarget();
      }
    },

    methods: {
      __getVirtualScrollEl: function __getVirtualScrollEl () {
        return this.$el
      },

      __getVirtualScrollTarget: function __getVirtualScrollTarget () {
        return this.__scrollTarget
      },

      __configureScrollTarget: function __configureScrollTarget () {
        this.__scrollTarget = getScrollTarget(this.$el, this.scrollTarget);
        this.__scrollTarget.addEventListener('scroll', this.__onVirtualScrollEvt, listenOpts.passive);
      },

      __unconfigureScrollTarget: function __unconfigureScrollTarget () {
        if (this.__scrollTarget !== void 0) {
          this.__scrollTarget.removeEventListener('scroll', this.__onVirtualScrollEvt, listenOpts.passive);
          this.__scrollTarget = void 0;
        }
      }
    },

    beforeMount: function beforeMount () {
      this.__resetVirtualScroll();
    },

    mounted: function mounted () {
      this.__configureScrollTarget();
    },

    beforeDestroy: function beforeDestroy () {
      this.__unconfigureScrollTarget();
    },

    render: function render (h) {
      if (this.$scopedSlots.default === void 0) {
        console.error("QVirtualScroll: default scoped slot is required for rendering", this);
        return
      }

      var child = this.__padVirtualScroll(
        h,
        this.type === 'list' ? 'div' : 'tbody',
        this.virtualScrollScope.map(this.$scopedSlots.default)
      );

      if (this.$scopedSlots.before !== void 0) {
        child = this.$scopedSlots.before().concat(child);
      }

      child = mergeSlot(child, this, 'after');

      return this.type === '__qtable'
        ? getTableMiddle(h, { staticClass: this.classes }, child)
        : h(comps[this.type], {
          class: this.classes,
          attrs: this.attrs,
          props: this.$attrs,
          on: this.$listeners
        }, child)
    }
  });

  function sortDate (a, b) {
    return (new Date(a)) - (new Date(b))
  }

  var Sort = {
    props: {
      sortMethod: {
        type: Function,
        default: function default$1 (data, sortBy, descending) {
          var col = this.columns.find(function (def) { return def.name === sortBy; });
          if (col === void 0 || col.field === void 0) {
            return data
          }

          var
            dir = descending === true ? -1 : 1,
            val = typeof col.field === 'function'
              ? function (v) { return col.field(v); }
              : function (v) { return v[col.field]; };

          return data.sort(function (a, b) {
            var assign;

            var
              A = val(a),
              B = val(b);

            if (A === null || A === void 0) {
              return -1 * dir
            }
            if (B === null || B === void 0) {
              return 1 * dir
            }
            if (col.sort !== void 0) {
              return col.sort(A, B, a, b) * dir
            }
            if (isNumber(A) === true && isNumber(B) === true) {
              return (A - B) * dir
            }
            if (isDate(A) === true && isDate(B) === true) {
              return sortDate(A, B) * dir
            }
            if (typeof A === 'boolean' && typeof B === 'boolean') {
              return (A - B) * dir
            }

            (assign = [A, B].map(function (s) { return (s + '').toLocaleString().toLowerCase(); }), A = assign[0], B = assign[1]);

            return A < B
              ? -1 * dir
              : (A === B ? 0 : dir)
          })
        }
      }
    },

    computed: {
      columnToSort: function columnToSort () {
        var ref = this.computedPagination;
        var sortBy = ref.sortBy;

        if (sortBy) {
          return this.columns.find(function (def) { return def.name === sortBy; }) || null
        }
      }
    },

    methods: {
      sort: function sort (col /* String(col name) or Object(col definition) */) {
        if (col === Object(col)) {
          col = col.name;
        }

        var ref = this.computedPagination;
        var sortBy = ref.sortBy;
        var descending = ref.descending;

        if (sortBy !== col) {
          sortBy = col;
          descending = false;
        }
        else if (this.binaryStateSort === true) {
          descending = !descending;
        }
        else if (descending === true) {
          sortBy = null;
        }
        else {
          descending = true;
        }

        this.setPagination({ sortBy: sortBy, descending: descending, page: 1 });
      }
    }
  };

  var Filter = {
    props: {
      filter: [String, Object],
      filterMethod: {
        type: Function,
        default: function default$1 (rows, terms, cols, cellValue) {
          if ( cols === void 0 ) cols = this.computedCols;
          if ( cellValue === void 0 ) cellValue = this.getCellValue;

          var lowerTerms = terms ? terms.toLowerCase() : '';
          return rows.filter(
            function (row) { return cols.some(function (col) { return (cellValue(col, row) + '').toLowerCase().indexOf(lowerTerms) !== -1; }); }
          )
        }
      }
    },

    watch: {
      filter: {
        handler: function handler () {
          var this$1 = this;

          this.$nextTick(function () {
            this$1.setPagination({ page: 1 }, true);
          });
        },
        deep: true
      }
    }
  };

  function samePagination (oldPag, newPag) {
    for (var prop in newPag) {
      if (newPag[prop] !== oldPag[prop]) {
        return false
      }
    }
    return true
  }

  function fixPagination (p) {
    if (p.page < 1) {
      p.page = 1;
    }
    if (p.rowsPerPage !== void 0 && p.rowsPerPage < 1) {
      p.rowsPerPage = 0;
    }
    return p
  }

  var Pagination = {
    props: {
      pagination: Object,
      rowsPerPageOptions: {
        type: Array,
        default: function () { return [3, 5, 7, 10, 15, 20, 25, 50, 0]; }
      }
    },

    computed: {
      computedPagination: function computedPagination () {
        return fixPagination(Object.assign({}, this.innerPagination,
          this.pagination))
      },

      firstRowIndex: function firstRowIndex () {
        var ref = this.computedPagination;
        var page = ref.page;
        var rowsPerPage = ref.rowsPerPage;
        return (page - 1) * rowsPerPage
      },

      lastRowIndex: function lastRowIndex () {
        var ref = this.computedPagination;
        var page = ref.page;
        var rowsPerPage = ref.rowsPerPage;
        return page * rowsPerPage
      },

      isFirstPage: function isFirstPage () {
        return this.computedPagination.page === 1
      },

      pagesNumber: function pagesNumber () {
        return this.computedPagination.rowsPerPage === 0
          ? 1
          : Math.max(
            1,
            Math.ceil(this.computedRowsNumber / this.computedPagination.rowsPerPage)
          )
      },

      isLastPage: function isLastPage () {
        return this.lastRowIndex === 0
          ? true
          : this.computedPagination.page >= this.pagesNumber
      },

      computedRowsPerPageOptions: function computedRowsPerPageOptions () {
        var this$1 = this;

        return this.rowsPerPageOptions.map(function (count) { return ({
          label: count === 0 ? this$1.$q.lang.table.allRows : '' + count,
          value: count
        }); })
      }
    },

    watch: {
      pagesNumber: function pagesNumber (lastPage, oldLastPage) {
        if (lastPage === oldLastPage) {
          return
        }

        var currentPage = this.computedPagination.page;
        if (lastPage && !currentPage) {
          this.setPagination({ page: 1 });
        }
        else if (lastPage < currentPage) {
          this.setPagination({ page: lastPage });
        }
      }
    },

    methods: {
      __sendServerRequest: function __sendServerRequest (pagination) {
        this.requestServerInteraction({
          pagination: pagination,
          filter: this.filter
        });
      },

      setPagination: function setPagination (val, forceServerRequest) {
        var newPagination = fixPagination(Object.assign({}, this.computedPagination,
          val));

        if (samePagination(this.computedPagination, newPagination)) {
          if (this.isServerSide && forceServerRequest) {
            this.__sendServerRequest(newPagination);
          }
          return
        }

        if (this.isServerSide) {
          this.__sendServerRequest(newPagination);
          return
        }

        if (this.pagination) {
          this.$emit('update:pagination', newPagination);
        }
        else {
          this.innerPagination = newPagination;
        }
      },

      prevPage: function prevPage () {
        var ref = this.computedPagination;
        var page = ref.page;
        if (page > 1) {
          this.setPagination({ page: page - 1 });
        }
      },

      nextPage: function nextPage () {
        var ref = this.computedPagination;
        var page = ref.page;
        var rowsPerPage = ref.rowsPerPage;
        if (this.lastRowIndex > 0 && page * rowsPerPage < this.computedRowsNumber) {
          this.setPagination({ page: page + 1 });
        }
      }
    },

    created: function created () {
      this.$emit('update:pagination', Object.assign({}, this.computedPagination));
    }
  };

  var RowSelection = {
    props: {
      selection: {
        type: String,
        default: 'none',
        validator: function (v) { return ['single', 'multiple', 'none'].includes(v); }
      },
      selected: {
        type: Array,
        default: function () { return []; }
      }
    },

    computed: {
      selectedKeys: function selectedKeys () {
        var keys = {};
        this.selected.map(this.getRowKey).forEach(function (key) {
          keys[key] = true;
        });
        return keys
      },

      hasSelectionMode: function hasSelectionMode () {
        return this.selection !== 'none'
      },

      singleSelection: function singleSelection () {
        return this.selection === 'single'
      },

      multipleSelection: function multipleSelection () {
        return this.selection === 'multiple'
      },

      allRowsSelected: function allRowsSelected () {
        var this$1 = this;

        return this.computedRows.length > 0 && this.computedRows.every(
          function (row) { return this$1.selectedKeys[ this$1.getRowKey(row) ] === true; }
        )
      },

      someRowsSelected: function someRowsSelected () {
        var this$1 = this;

        return this.allRowsSelected !== true &&
          this.computedRows.some(function (row) { return this$1.selectedKeys[ this$1.getRowKey(row) ] === true; })
      },

      rowsSelectedNumber: function rowsSelectedNumber () {
        return this.selected.length
      }
    },

    methods: {
      isRowSelected: function isRowSelected (key) {
        return this.selectedKeys[key] === true
      },

      clearSelection: function clearSelection () {
        this.$emit('update:selected', []);
      },

      __updateSelection: function __updateSelection (keys, rows, added) {
        var this$1 = this;

        this.$emit('selection', { rows: rows, added: added, keys: keys });

        var payload = this.singleSelection === true
          ? (added === true ? rows : [])
          : (
            added === true
              ? this.selected.concat(rows)
              : this.selected.filter(
                function (row) { return keys.includes(this$1.getRowKey(row)) === false; }
              )
          );

        this.$emit('update:selected', payload);
      }
    }
  };

  function getVal (val) {
    return Array.isArray(val)
      ? val.slice()
      : []
  }

  var RowExpand = {
    props: {
      expanded: Array // sync
    },

    data: function data () {
      return {
        innerExpanded: getVal(this.expanded)
      }
    },

    watch: {
      expanded: function expanded (val) {
        this.innerExpanded = getVal(val);
      }
    },

    methods: {
      isRowExpanded: function isRowExpanded (key) {
        return this.innerExpanded.includes(key)
      },

      setExpanded: function setExpanded (val) {
        if (this.expanded !== void 0) {
          this.$emit('update:expanded', val);
        }
        else {
          this.innerExpanded = val;
        }
      },

      __updateExpanded: function __updateExpanded (key, add) {
        var target = this.innerExpanded.slice();
        var index = target.indexOf(key);

        if (add === true) {
          if (index === -1) {
            target.push(key);
            this.setExpanded(target);
          }
        }
        else if (index !== -1) {
          target.splice(index, 1);
          this.setExpanded(target);
        }
      }
    }
  };

  var ColumnSelection = {
    props: {
      visibleColumns: Array
    },

    computed: {
      computedCols: function computedCols () {
        var this$1 = this;

        var ref = this.computedPagination;
        var sortBy = ref.sortBy;
        var descending = ref.descending;

        var cols = this.visibleColumns !== void 0
          ? this.columns.filter(function (col) { return col.required === true || this$1.visibleColumns.includes(col.name) === true; })
          : this.columns;

        return cols.map(function (col) {
          col.align = col.align || 'right';
          col.__iconClass = "q-table__sort-icon q-table__sort-icon--" + (col.align);
          col.__thClass = "text-" + (col.align) + (col.headerClasses !== void 0 ? ' ' + col.headerClasses : '') + (col.sortable === true ? ' sortable' : '') + (col.name === sortBy ? (" sorted " + (descending === true ? 'sort-desc' : '')) : '');
          col.__tdClass = "text-" + (col.align) + (col.classes !== void 0 ? ' ' + col.classes : '');
          col.__thStyle = col.headerStyle !== void 0 ? col.headerStyle : null;
          col.__tdStyle = col.style !== void 0 ? col.style : null;
          return col
        })
      },

      computedColsMap: function computedColsMap () {
        var names = {};
        this.computedCols.forEach(function (col) {
          names[col.name] = col;
        });
        return names
      }
    }
  };

  var commonVirtPropsObj = {};
  commonVirtPropsList.forEach(function (p) { commonVirtPropsObj[p] = {}; });

  var QTable = Vue.extend({
    name: 'QTable',

    mixins: [
      DarkMixin,

      FullscreenMixin,
      Top,
      TableHeader,
      TableBody,
      Bottom,
      TableGrid,
      Sort,
      Filter,
      Pagination,
      RowSelection,
      RowExpand,
      ColumnSelection
    ],

    props: Object.assign({}, {data: {
        type: Array,
        default: function () { return []; }
      },
      rowKey: {
        type: [ String, Function ],
        default: 'id'
      },

      columns: Array,
      loading: Boolean,
      binaryStateSort: Boolean,

      title: String,

      hideHeader: Boolean,
      hideBottom: Boolean,

      grid: Boolean,
      gridHeader: Boolean,

      dense: Boolean,
      flat: Boolean,
      bordered: Boolean,
      square: Boolean,
      separator: {
        type: String,
        default: 'horizontal',
        validator: function (v) { return ['horizontal', 'vertical', 'cell', 'none'].includes(v); }
      },
      wrapCells: Boolean,

      virtualScroll: Boolean},
      commonVirtPropsObj,

      {noDataLabel: String,
      noResultsLabel: String,
      loadingLabel: String,
      selectedRowsLabel: Function,
      rowsPerPageLabel: String,
      paginationLabel: Function,

      color: {
        type: String,
        default: 'grey-8'
      },

      tableStyle: [String, Array, Object],
      tableClass: [String, Array, Object],
      tableHeaderStyle: [String, Array, Object],
      tableHeaderClass: [String, Array, Object],
      cardContainerClass: [String, Array, Object],
      cardContainerStyle: [String, Array, Object],
      cardStyle: [String, Array, Object],
      cardClass: [String, Array, Object]}),

    data: function data () {
      return {
        innerPagination: {
          sortBy: null,
          descending: false,
          page: 1,
          rowsPerPage: 5
        }
      }
    },

    watch: {
      needsReset: function needsReset () {
        this.hasVirtScroll === true && this.$refs.virtScroll !== void 0 && this.$refs.virtScroll.reset();
      }
    },

    computed: {
      getRowKey: function getRowKey () {
        var this$1 = this;

        return typeof this.rowKey === 'function'
          ? this.rowKey
          : function (row) { return row[this$1.rowKey]; }
      },

      hasVirtScroll: function hasVirtScroll () {
        return this.grid !== true && this.virtualScroll === true
      },

      needsReset: function needsReset () {
        var this$1 = this;

        return ['tableStyle', 'tableClass', 'tableHeaderStyle', 'tableHeaderClass', 'containerClass']
          .map(function (p) { return this$1[p]; }).join(';')
      },

      computedData: function computedData () {
        var rows = this.data;

        if (rows.length === 0) {
          return {
            rowsNumber: 0,
            rows: rows
          }
        }

        if (this.isServerSide === true) {
          return {
            rowsNumber: rows.length,
            rows: rows
          }
        }

        var ref = this.computedPagination;
        var sortBy = ref.sortBy;
        var descending = ref.descending;
        var rowsPerPage = ref.rowsPerPage;

        if (this.filter) {
          rows = this.filterMethod(rows, this.filter, this.computedCols, this.getCellValue);
        }

        if (this.columnToSort !== void 0) {
          rows = this.sortMethod(
            this.data === rows ? rows.slice() : rows,
            sortBy,
            descending
          );
        }

        var rowsNumber = rows.length;

        if (rowsPerPage !== 0) {
          if (this.firstRowIndex === 0 && this.data !== rows) {
            if (rows.length > this.lastRowIndex) {
              rows.length = this.lastRowIndex;
            }
          }
          else {
            rows = rows.slice(this.firstRowIndex, this.lastRowIndex);
          }
        }

        return { rowsNumber: rowsNumber, rows: rows }
      },

      computedRows: function computedRows () {
        return this.computedData.rows
      },

      computedRowsNumber: function computedRowsNumber () {
        return this.isServerSide === true
          ? this.computedPagination.rowsNumber || 0
          : this.computedData.rowsNumber
      },

      nothingToDisplay: function nothingToDisplay () {
        return this.computedRows.length === 0
      },

      isServerSide: function isServerSide () {
        return this.computedPagination.rowsNumber !== void 0
      },

      cardDefaultClass: function cardDefaultClass () {
        return " q-table__card" +
          (this.isDark === true ? ' q-table__card--dark q-dark' : '') +
          (this.square === true ? " q-table--square" : '') +
          (this.flat === true ? " q-table--flat" : '') +
          (this.bordered === true ? " q-table--bordered" : '')
      },

      containerClass: function containerClass () {
        return "q-table__container q-table--" + (this.separator) + "-separator column no-wrap" +
          (this.loading === true ? ' q-table--loading' : '') +
          (this.grid === true ? ' q-table--grid' : this.cardDefaultClass) +
          (this.isDark === true ? " q-table--dark" : '') +
          (this.dense === true ? " q-table--dense" : '') +
          (this.wrapCells === false ? " q-table--no-wrap" : '') +
          (this.inFullscreen === true ? " fullscreen scroll" : '')
      },

      virtProps: function virtProps () {
        var this$1 = this;

        var props = {};

        commonVirtPropsList
          .forEach(function (p) { props[p] = this$1[p]; });

        if (props.virtualScrollItemSize === void 0) {
          props.virtualScrollItemSize = this.dense === true ? 28 : 48;
        }

        return props
      }
    },

    render: function render (h) {
      var child = [ this.getTop(h) ];
      var data = { staticClass: this.containerClass };

      if (this.grid === true) {
        child.push(this.getGridHeader(h));
      }
      else {
        Object.assign(data, {
          class: this.cardClass,
          style: this.cardStyle
        });
      }

      child.push(
        this.getBody(h),
        this.getBottom(h)
      );

      if (this.loading === true && this.$scopedSlots.loading !== void 0) {
        child.push(
          this.$scopedSlots.loading()
        );
      }

      return h('div', data, child)
    },

    methods: {
      requestServerInteraction: function requestServerInteraction (prop) {
        var this$1 = this;
        if ( prop === void 0 ) prop = {};

        this.$nextTick(function () {
          this$1.$emit('request', {
            pagination: prop.pagination || this$1.computedPagination,
            filter: prop.filter || this$1.filter,
            getCellValue: this$1.getCellValue
          });
        });
      },

      resetVirtualScroll: function resetVirtualScroll () {
        this.hasVirtScroll === true && this.$refs.virtScroll.reset();
      },

      getBody: function getBody (h) {
        if (this.grid === true) {
          return this.getGridBody(h)
        }

        var header = this.hideHeader !== true ? this.getTableHeader(h) : null;

        return this.hasVirtScroll === true
          ? h(QVirtualScroll, {
            ref: 'virtScroll',
            props: Object.assign({}, this.virtProps,
              {items: this.computedRows,
              type: '__qtable'}),
            on: cache(this, 'vs', {
              'virtual-scroll': this.__onVScroll
            }),
            class: this.tableClass,
            style: this.tableStyle,
            scopedSlots: {
              before: header === null
                ? void 0
                : function () { return header; },
              default: this.getTableRowVirtual(h)
            }
          })
          : getTableMiddle(h, {
            staticClass: 'scroll',
            class: this.tableClass,
            style: this.tableStyle
          }, [
            header,
            this.getTableBody(h)
          ])
      },

      scrollTo: function scrollTo (toIndex) {
        if (this.$refs.virtScroll !== void 0) {
          this.$refs.virtScroll.scrollTo(toIndex);
          return
        }

        toIndex = parseInt(toIndex, 10);
        var rowEl = this.$el.querySelector(("tbody tr:nth-of-type(" + (toIndex + 1) + ")"));

        if (rowEl !== null) {
          var scrollTarget = this.$el.querySelector('.q-table__middle.scroll');
          var offsetTop = rowEl.offsetTop;
          var direction = offsetTop < scrollTarget.scrollTop ? 'decrease' : 'increase';

          scrollTarget.scrollTop = offsetTop;

          this.$emit('virtual-scroll', {
            index: toIndex,
            from: 0,
            to: this.pagination.rowsPerPage - 1,
            direction: direction
          });
        }
      },

      __onVScroll: function __onVScroll (info) {
        this.$emit('virtual-scroll', info);
      },

      __getProgress: function __getProgress (h) {
        return [
          h(QLinearProgress, {
            staticClass: 'q-table__linear-progress',
            props: {
              color: this.color,
              dark: this.isDark,
              indeterminate: true,
              trackColor: 'transparent'
            }
          })
        ]
      }
    }
  });

  var QTr = Vue.extend({
    name: 'QTr',

    props: {
      props: Object,
      noHover: Boolean
    },

    computed: {
      classes: function classes () {
        return 'q-tr' + (this.props === void 0 || this.props.header === true ? '' : ' ' + this.props.__trClass) +
          (this.noHover === true ? ' q-tr--no-hover' : '')
      }
    },

    render: function render (h) {
      return h('tr', {
        on: this.$listeners,
        class: this.classes
      }, slot(this, 'default'))
    }
  });

  var QTd = Vue.extend({
    name: 'QTd',

    props: {
      props: Object,
      autoWidth: Boolean,
      noHover: Boolean
    },

    computed: {
      classes: function classes () {
        return 'q-td' + (this.autoWidth === true ? ' q-table--col-auto-width' : '') +
          (this.noHover === true ? ' q-td--no-hover' : '')
      }
    },

    render: function render (h) {
      var on = this.$listeners;

      if (this.props === void 0) {
        return h('td', {
          on: on,
          class: this.classes
        }, slot(this, 'default'))
      }

      var name = this.$vnode.key;

      var col = this.props.colsMap !== void 0 && name
        ? this.props.colsMap[name]
        : this.props.col;

      if (col === void 0) { return }

      return h('td', {
        on: on,
        style: col.__tdStyle,
        class: this.classes + ' ' + col.__tdClass
      }, slot(this, 'default'))
    }
  });

  var trailingSlashRE = /\/?$/;

  function queryIncludes (current, target) {
    for (var key in target) {
      if (!(key in current)) {
        return false
      }
    }
    return true
  }

  function isSameRoute (current, target) {
    if (!target) {
      return false
    }
    if (current.path && target.path) {
      return (
        current.path.replace(trailingSlashRE, '') === target.path.replace(trailingSlashRE, '') &&
        current.hash === target.hash &&
        isDeepEqual(current.query, target.query)
      )
    }
    if (current.name && target.name) {
      return (
        current.name === target.name &&
        current.hash === target.hash &&
        isDeepEqual(current.query, target.query) &&
        isDeepEqual(current.params, target.params)
      )
    }
    return false
  }

  function isIncludedRoute (current, target) {
    return (
      current.path.replace(trailingSlashRE, '/').indexOf(target.path.replace(trailingSlashRE, '/')) === 0 &&
      (!target.hash || current.hash === target.hash) &&
      queryIncludes(current.query, target.query)
    )
  }

  var QRouteTab = Vue.extend({
    name: 'QRouteTab',

    mixins: [ QTab, RouterLinkMixin ],

    props: {
      to: { required: true }
    },

    inject: {
      __activateRoute: {},
      __recalculateScroll: {}
    },

    watch: {
      $route: function $route () {
        this.__checkActivation();
      }
    },

    methods: {
      __activate: function __activate (e, keyboard) {
        if (this.disable !== true) {
          this.__checkActivation(true);
        }

        if (keyboard === true) {
          this.$el.focus(e);
        }
        else {
          this.$refs.blurTarget !== void 0 && this.$refs.blurTarget.focus(e);
        }
      },

      __checkActivation: function __checkActivation (selected) {
        if ( selected === void 0 ) selected = false;

        var
          current = this.$route;
        var ref = this.$router.resolve(this.to, current, this.append);
        var href = ref.href;
        var location = ref.location;
        var route = ref.route;
        var redirected = route.redirectedFrom !== void 0,
          checkFunction = this.exact === true ? isSameRoute : isIncludedRoute,
          params = {
            name: this.name,
            selected: selected,
            exact: this.exact,
            priorityMatched: route.matched.length,
            priorityHref: href.length
          };

        checkFunction(current, route) && this.__activateRoute(Object.assign({}, params, {redirected: redirected}));
        redirected === true && checkFunction(current, Object.assign({}, {path: route.redirectedFrom},
          location)) && this.__activateRoute(params);
        this.isActive && this.__activateRoute();
      }
    },

    mounted: function mounted () {
      this.__recalculateScroll();
      this.$router !== void 0 && this.__checkActivation();
    },

    beforeDestroy: function beforeDestroy () {
      this.__recalculateScroll();
      this.__activateRoute({ remove: true, name: this.name });
    },

    render: function render (h) {
      return this.__renderTab(h, 'router-link', this.routerLinkProps)
    }
  });

  var QTime = Vue.extend({
    name: 'QTime',

    mixins: [ DateTimeMixin ],

    directives: {
      TouchPan: TouchPan
    },

    props: {
      mask: {
        default: null
      },

      format24h: {
        type: Boolean,
        default: null
      },

      defaultDate: {
        type: String,
        validator: function (v) { return /^-?[\d]+\/[0-1]\d\/[0-3]\d$/.test(v); }
      },

      options: Function,
      hourOptions: Array,
      minuteOptions: Array,
      secondOptions: Array,

      withSeconds: Boolean,
      nowBtn: Boolean
    },

    data: function data () {
      var model = __splitDate(
        this.value,
        this.__getComputedMask(),
        this.__getComputedLocale(),
        this.calendar,
        this.__getDefaultDateModel()
      );

      var view = 'Hour';

      if (model.hour !== null) {
        if (model.minute === null) {
          view = 'Minute';
        }
        else if (this.withSeconds === true && model.second === null) {
          view = 'Second';
        }
      }

      return {
        view: view,
        isAM: model.hour === null || model.hour < 12,
        innerModel: model
      }
    },

    watch: {
      value: function value (v) {
        var model = __splitDate(
          v,
          this.computedMask,
          this.computedLocale,
          this.calendar,
          this.defaultDateModel
        );

        if (
          model.dateHash !== this.innerModel.dateHash ||
          model.timeHash !== this.innerModel.timeHash
        ) {
          this.innerModel = model;

          if (model.hour === null) {
            this.view = 'Hour';
          }
          else {
            this.isAM = model.hour < 12;
          }
        }
      }
    },

    computed: {
      classes: function classes () {
        return "q-time q-time--" + (this.landscape === true ? 'landscape' : 'portrait') +
          (this.isDark === true ? ' q-time--dark q-dark' : '') +
          (this.disable === true ? ' disabled' : (this.readonly === true ? ' q-time--readonly' : '')) +
          (this.bordered === true ? " q-time--bordered" : '') +
          (this.square === true ? " q-time--square no-border-radius" : '') +
          (this.flat === true ? " q-time--flat no-shadow" : '')
      },

      computedMask: function computedMask () {
        return this.__getComputedMask()
      },

      stringModel: function stringModel () {
        var time = this.innerModel;

        return {
          hour: time.hour === null
            ? '--'
            : (
              this.computedFormat24h === true
                ? pad(time.hour)
                : String(
                  this.isAM === true
                    ? (time.hour === 0 ? 12 : time.hour)
                    : (time.hour > 12 ? time.hour - 12 : time.hour)
                )
            ),
          minute: time.minute === null
            ? '--'
            : pad(time.minute),
          second: time.second === null
            ? '--'
            : pad(time.second)
        }
      },

      defaultDateModel: function defaultDateModel () {
        return this.__getDefaultDateModel()
      },

      computedFormat24h: function computedFormat24h () {
        return this.format24h !== null
          ? this.format24h
          : this.$q.lang.date.format24h
      },

      pointerStyle: function pointerStyle () {
        var
          forHour = this.view === 'Hour',
          divider = forHour === true ? 12 : 60,
          amount = this.innerModel[this.view.toLowerCase()],
          degrees = Math.round(amount * (360 / divider)) - 180;

        var transform = "rotate(" + degrees + "deg) translateX(-50%)";

        if (
          forHour === true &&
          this.computedFormat24h === true &&
          this.innerModel.hour >= 12
        ) {
          transform += ' scale(.7)';
        }

        return { transform: transform }
      },

      minLink: function minLink () {
        return this.innerModel.hour !== null
      },

      secLink: function secLink () {
        return this.minLink === true && this.innerModel.minute !== null
      },

      hourInSelection: function hourInSelection () {
        var this$1 = this;

        return this.hourOptions !== void 0
          ? function (val) { return this$1.hourOptions.includes(val); }
          : (
            this.options !== void 0
              ? function (val) { return this$1.options(val, null, null); }
              : void 0
          )
      },

      minuteInSelection: function minuteInSelection () {
        var this$1 = this;

        return this.minuteOptions !== void 0
          ? function (val) { return this$1.minuteOptions.includes(val); }
          : (
            this.options !== void 0
              ? function (val) { return this$1.options(this$1.innerModel.hour, val, null); }
              : void 0
          )
      },

      secondInSelection: function secondInSelection () {
        var this$1 = this;

        return this.secondOptions !== void 0
          ? function (val) { return this$1.secondOptions.includes(val); }
          : (
            this.options !== void 0
              ? function (val) { return this$1.options(this$1.innerModel.hour, this$1.innerModel.minute, val); }
              : void 0
          )
      },

      positions: function positions () {
        var start, end, offset = 0, step = 1, inSel;

        if (this.view === 'Hour') {
          inSel = this.hourInSelection;

          if (this.computedFormat24h === true) {
            start = 0;
            end = 23;
          }
          else {
            start = 0;
            end = 11;

            if (this.isAM === false) {
              offset = 12;
            }
          }
        }
        else {
          start = 0;
          end = 55;
          step = 5;

          if (this.view === 'Minute') {
            inSel = this.minuteInSelection;
          }
          else {
            inSel = this.secondInSelection;
          }
        }

        var pos = [];

        for (var val = start, index = start; val <= end; val += step, index++) {
          var
            actualVal = val + offset,
            disable = inSel !== void 0 && inSel(actualVal) === false,
            label = this.view === 'Hour' && val === 0
              ? (this.format24h === true ? '00' : '12')
              : val;

          pos.push({ val: actualVal, index: index, disable: disable, label: label });
        }

        return pos
      }
    },

    methods: {
      setNow: function setNow () {
        this.__updateValue(Object.assign({}, this.__getCurrentDate(),
          this.__getCurrentTime()));
        this.view = 'Hour';
      },

      __getDefaultDateModel: function __getDefaultDateModel () {
        if (typeof this.defaultDate !== 'string') {
          var date = this.__getCurrentDate();
          date.dateHash = date.year + '/' + pad(date.month) + '/' + pad(date.day);

          return date
        }

        return __splitDate(this.defaultDate, 'YYYY/MM/DD', void 0, this.calendar)
      },

      __click: function __click (evt) {
        // __activate() has already updated the offset
        // we only need to change the view now, so:

        if (this.$q.platform.is.desktop !== true) {
          this.__drag({ isFirst: true, evt: evt });
        }

        this.__drag({ isFinal: true, evt: evt });
      },

      __activate: function __activate (evt) {
        this.__drag({ isFirst: true, evt: evt }, true);
        this.__drag({ isFinal: true, evt: evt }, true);
      },

      __drag: function __drag (event, noViewChange) {
        // cases when on a popup getting closed
        // on previously emitted value
        if (this._isBeingDestroyed === true || this._isDestroyed === true) {
          return
        }

        if (event.isFirst) {
          var
            clock = this.$refs.clock;
          var ref = clock.getBoundingClientRect();
          var top = ref.top;
          var left = ref.left;
          var width = ref.width;
          var dist = width / 2;

          this.dragging = {
            top: top + dist,
            left: left + dist,
            dist: dist * 0.7
          };
          this.dragCache = null;
          this.__updateClock(event.evt);
          return
        }

        this.__updateClock(event.evt);

        if (event.isFinal && noViewChange !== true) {
          this.dragging = false;

          if (this.view === 'Hour') {
            this.view = 'Minute';
          }
          else if (this.withSeconds && this.view === 'Minute') {
            this.view = 'Second';
          }
        }
      },

      __updateClock: function __updateClock (evt) {
        var
          val,
          pos = position(evt),
          height = Math.abs(pos.top - this.dragging.top),
          distance = Math.sqrt(
            Math.pow(Math.abs(pos.top - this.dragging.top), 2) +
            Math.pow(Math.abs(pos.left - this.dragging.left), 2)
          ),
          angle = Math.asin(height / distance) * (180 / Math.PI);

        if (pos.top < this.dragging.top) {
          angle = this.dragging.left < pos.left ? 90 - angle : 270 + angle;
        }
        else {
          angle = this.dragging.left < pos.left ? angle + 90 : 270 - angle;
        }

        if (this.view === 'Hour') {
          val = Math.round(angle / 30);

          if (this.computedFormat24h === true) {
            if (distance < this.dragging.dist) {
              if (val < 12) {
                val += 12;
              }
            }
            else if (val === 12) {
              val = 0;
            }
            this.isAM = val < 12;
          }
          else if (this.isAM === true && val === 12) {
            val = 0;
          }
          else if (this.isAM === false && val !== 12) {
            val += 12;
          }
        }
        else {
          val = Math.round(angle / 6);

          if (val === 60) {
            val = 0;
          }
        }

        if (this.dragCache === val) {
          return
        }

        var opt = this[((this.view.toLowerCase()) + "InSelection")];

        if (opt !== void 0 && opt(val) !== true) {
          return
        }

        this.dragCache = val;
        this[("__set" + (this.view))](val);
      },

      __onKeyupHour: function __onKeyupHour (e) {
        if (e.keyCode === 13) { // ENTER
          this.view = 'Hour';
        }
        else {
          var
            wrap = this.computedFormat24h === true ? 24 : 12,
            offset = this.computedFormat24h !== true && this.isAM === false ? 12 : 0;

          if (e.keyCode === 37) { // ARROW LEFT
            this.__setHour(offset + (24 + this.innerModel.hour - 1) % wrap);
          }
          else if (e.keyCode === 39) { // ARROW RIGHT
            this.__setHour(offset + (24 + this.innerModel.hour + 1) % wrap);
          }
        }
      },

      __onKeyupMinute: function __onKeyupMinute (e) {
        if (e.keyCode === 13) { // ENTER
          this.view = 'Minute';
        }
        else if (e.keyCode === 37) { // ARROW LEFT
          this.__setMinute((60 + this.innerModel.minute - 1) % 60);
        }
        else if (e.keyCode === 39) { // ARROW RIGHT
          this.__setMinute((60 + this.innerModel.minute + 1) % 60);
        }
      },

      __onKeyupSecond: function __onKeyupSecond (e) {
        if (e.keyCode === 13) { // ENTER
          this.view = 'Second';
        }
        else if (e.keyCode === 37) { // ARROW LEFT
          this.__setSecond((60 + this.innerModel.second - 1) % 60);
        }
        else if (e.keyCode === 39) { // ARROW RIGHT
          this.__setSecond((60 + this.innerModel.second + 1) % 60);
        }
      },

      __getHeader: function __getHeader (h) {
        var this$1 = this;

        var label = [
          h('div', {
            staticClass: 'q-time__link',
            class: this.view === 'Hour' ? 'q-time__link--active' : 'cursor-pointer',
            attrs: { tabindex: this.computedTabindex },
            on: cache(this, 'vH', {
              click: function () { this$1.view = 'Hour'; },
              keyup: this.__onKeyupHour
            })
          }, [ this.stringModel.hour ]),

          h('div', [ ':' ]),

          h(
            'div',
            this.minLink === true
              ? {
                staticClass: 'q-time__link',
                class: this.view === 'Minute' ? 'q-time__link--active' : 'cursor-pointer',
                attrs: { tabindex: this.computedTabindex },
                on: cache(this, 'vM', {
                  click: function () { this$1.view = 'Minute'; },
                  keyup: this.__onKeyupMinute
                })
              }
              : { staticClass: 'q-time__link' },
            [ this.stringModel.minute ]
          )
        ];

        if (this.withSeconds === true) {
          label.push(
            h('div', [ ':' ]),

            h(
              'div',
              this.secLink === true
                ? {
                  staticClass: 'q-time__link',
                  class: this.view === 'Second' ? 'q-time__link--active' : 'cursor-pointer',
                  attrs: { tabindex: this.computedTabindex },
                  on: cache(this, 'vS', {
                    click: function () { this$1.view = 'Second'; },
                    keyup: this.__onKeyupSecond
                  })
                }
                : { staticClass: 'q-time__link' },
              [ this.stringModel.second ]
            )
          );
        }

        return h('div', {
          staticClass: 'q-time__header flex flex-center no-wrap',
          class: this.headerClass
        }, [
          h('div', {
            staticClass: 'q-time__header-label row items-center no-wrap',
            attrs: { dir: 'ltr' }
          }, label),

          this.computedFormat24h === false ? h('div', {
            staticClass: 'q-time__header-ampm column items-between no-wrap'
          }, [
            h('div', {
              staticClass: 'q-time__link',
              class: this.isAM === true ? 'q-time__link--active' : 'cursor-pointer',
              attrs: { tabindex: this.computedTabindex },
              on: cache(this, 'AM', {
                click: this.__setAm,
                keyup: function (e) { e.keyCode === 13 && this$1.__setAm(); }
              })
            }, [ 'AM' ]),

            h('div', {
              staticClass: 'q-time__link',
              class: this.isAM !== true ? 'q-time__link--active' : 'cursor-pointer',
              attrs: { tabindex: this.computedTabindex },
              on: cache(this, 'PM', {
                click: this.__setPm,
                keyup: function (e) { e.keyCode === 13 && this$1.__setPm(); }
              })
            }, [ 'PM' ])
          ]) : null
        ])
      },

      __getClock: function __getClock (h) {
        var this$1 = this;

        var
          view = this.view.toLowerCase(),
          current = this.innerModel[view];

        return h('div', {
          staticClass: 'q-time__content col relative-position'
        }, [
          h('transition', {
            props: { name: 'q-transition--scale' }
          }, [
            h('div', {
              key: 'clock' + this.view,
              staticClass: 'q-time__container-parent absolute-full'
            }, [
              h('div', {
                ref: 'clock',
                staticClass: 'q-time__container-child fit overflow-hidden'
              }, [
                h('div', {
                  staticClass: 'q-time__clock cursor-pointer non-selectable',
                  on: cache(this, 'click', {
                    click: this.__click,
                    mousedown: this.__activate
                  }),
                  directives: cache(this, 'touch', [{
                    name: 'touch-pan',
                    value: this.__drag,
                    modifiers: {
                      stop: true,
                      prevent: true,
                      mouse: true
                    }
                  }])
                }, [
                  h('div', { staticClass: 'q-time__clock-circle fit' }, [
                    h('div', {
                      staticClass: 'q-time__clock-pointer',
                      style: this.pointerStyle,
                      class: this.innerModel[view] === null ? 'hidden' : (this.color !== void 0 ? ("text-" + (this.color)) : '')
                    }),

                    this.positions.map(function (pos) { return h('div', {
                      staticClass: ("q-time__clock-position row flex-center q-time__clock-pos-" + (pos.index)),
                      class: pos.val === current
                        ? this$1.headerClass.concat(' q-time__clock-position--active')
                        : (pos.disable === true ? 'q-time__clock-position--disable' : null)
                    }, [ h('span', [ pos.label ]) ]); })
                  ])
                ])
              ])
            ])
          ]),

          this.nowBtn === true ? h(QBtn, {
            staticClass: 'q-time__now-button absolute',
            props: {
              icon: this.$q.iconSet.datetime.now,
              unelevated: true,
              size: 'sm',
              round: true,
              color: this.color,
              textColor: this.textColor,
              tabindex: this.computedTabindex
            },
            on: cache(this, 'now', {
              click: this.setNow
            })
          }) : null
        ])
      },

      __setHour: function __setHour (hour) {
        if (this.innerModel.hour !== hour) {
          this.innerModel.hour = hour;
          this.innerModel.minute = null;
          this.innerModel.second = null;
        }
      },

      __setMinute: function __setMinute (minute) {
        if (this.innerModel.minute !== minute) {
          this.innerModel.minute = minute;
          this.innerModel.second = null;
          this.withSeconds !== true && this.__updateValue({ minute: minute });
        }
      },

      __setSecond: function __setSecond (second) {
        this.innerModel.second !== second && this.__updateValue({ second: second });
      },

      __setAm: function __setAm () {
        if (this.isAM) { return }

        this.isAM = true;

        if (this.innerModel.hour === null) { return }
        this.innerModel.hour -= 12;
        this.__verifyAndUpdate();
      },

      __setPm: function __setPm () {
        if (!this.isAM) { return }

        this.isAM = false;

        if (this.innerModel.hour === null) { return }
        this.innerModel.hour += 12;
        this.__verifyAndUpdate();
      },

      __verifyAndUpdate: function __verifyAndUpdate () {
        if (this.hourInSelection !== void 0 && this.hourInSelection(this.innerModel.hour) !== true) {
          this.innerModel = __splitDate();
          this.isAM = true;
          this.view = 'Hour';
          return
        }

        if (this.minuteInSelection !== void 0 && this.minuteInSelection(this.innerModel.minute) !== true) {
          this.innerModel.minute = null;
          this.innerModel.second = null;
          this.view = 'Minute';
          return
        }

        if (this.withSeconds === true && this.secondInSelection !== void 0 && this.secondInSelection(this.innerModel.second) !== true) {
          this.innerModel.second = null;
          this.view = 'Second';
          return
        }

        if (this.innerModel.hour === null || this.innerModel.minute === null || (this.withSeconds === true && this.innerModel.second === null)) {
          return
        }

        this.__updateValue({});
      },

      __getComputedMask: function __getComputedMask () {
        return this.calendar !== 'persian' && this.mask !== null
          ? this.mask
          : ("HH:mm" + (this.withSeconds === true ? ':ss' : ''))
      },

      __updateValue: function __updateValue (obj) {
        var date = Object.assign({}, this.innerModel,
          obj);

        var val = this.calendar === 'persian'
          ? pad(date.hour) + ':' +
            pad(date.minute) +
            (this.withSeconds === true ? ':' + pad(date.second) : '')
          : formatDate(
            new Date(
              date.year,
              date.month === null ? null : date.month - 1,
              date.day,
              date.hour,
              date.minute,
              date.second,
              date.millisecond
            ),
            this.computedMask,
            this.computedLocale,
            date.year
          );

        date.changed = val !== this.value;
        this.$emit('input', val, date);
      }
    },

    render: function render (h) {
      var child = [
        this.__getClock(h)
      ];

      var def = slot(this, 'default');
      def !== void 0 && child.push(
        h('div', { staticClass: 'q-time__actions' }, def)
      );

      if (this.name !== void 0 && this.disable !== true) {
        this.__injectFormInput(child, 'push');
      }

      return h('div', {
        class: this.classes,
        on: this.$listeners,
        attrs: { tabindex: -1 }
      }, [
        this.__getHeader(h),
        h('div', { staticClass: 'q-time__main col overflow-auto' }, child)
      ])
    }
  });

  var QTimeline = Vue.extend({
    name: 'QTimeline',

    mixins: [ DarkMixin ],

    provide: function provide () {
      return {
        __timeline: this
      }
    },

    props: {
      color: {
        type: String,
        default: 'primary'
      },
      side: {
        type: String,
        default: 'right',
        validator: function (v) { return ['left', 'right'].includes(v); }
      },
      layout: {
        type: String,
        default: 'dense',
        validator: function (v) { return ['dense', 'comfortable', 'loose'].includes(v); }
      }
    },

    computed: {
      classes: function classes () {
        return "q-timeline--" + (this.layout) + " q-timeline--" + (this.layout) + "--" + (this.side) +
          (this.isDark === true ? ' q-timeline--dark' : '')
      }
    },

    render: function render (h) {
      return h('ul', {
        staticClass: 'q-timeline',
        class: this.classes,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QTimelineEntry = Vue.extend({
    name: 'QTimelineEntry',

    inject: {
      __timeline: {
        default: function default$1 () {
          console.error('QTimelineEntry needs to be child of QTimeline');
        }
      }
    },

    props: {
      heading: Boolean,
      tag: {
        type: String,
        default: 'h3'
      },
      side: {
        type: String,
        default: 'right',
        validator: function (v) { return ['left', 'right'].includes(v); }
      },

      icon: String,
      avatar: String,

      color: String,

      title: String,
      subtitle: String,
      body: String
    },

    computed: {
      colorClass: function colorClass () {
        return ("text-" + (this.color || this.__timeline.color))
      },

      classes: function classes () {
        return "q-timeline__entry--" + (this.side) +
          (this.icon !== void 0 || this.avatar !== void 0 ? ' q-timeline__entry--icon' : '')
      },

      reverse: function reverse () {
        return this.__timeline.layout === 'comfortable' && this.__timeline.side === 'left'
      }
    },

    render: function render (h) {
      var child = uniqueSlot(this, 'default', []);

      if (this.body !== void 0) {
        child.unshift(this.body);
      }

      if (this.heading === true) {
        var content$1 = [
          h('div'),
          h('div'),
          h(
            this.tag,
            { staticClass: 'q-timeline__heading-title' },
            child
          )
        ];

        return h('div', {
          staticClass: 'q-timeline__heading',
          on: this.$listeners
        }, this.reverse === true ? content$1.reverse() : content$1)
      }

      var dot;

      if (this.icon !== void 0) {
        dot = [
          h(QIcon, {
            staticClass: 'row items-center justify-center',
            props: { name: this.icon }
          })
        ];
      }
      else if (this.avatar !== void 0) {
        dot = [
          h('img', {
            staticClass: 'q-timeline__dot-img',
            domProps: { src: this.avatar }
          })
        ];
      }

      var content = [
        h('div', { staticClass: 'q-timeline__subtitle' }, [
          h('span', slot(this, 'subtitle', [ this.subtitle ]))
        ]),

        h('div', {
          staticClass: 'q-timeline__dot',
          class: this.colorClass
        }, dot),

        h('div', { staticClass: 'q-timeline__content' }, [
          h('h6', { staticClass: 'q-timeline__title' }, slot(this, 'title', [ this.title ]))
        ].concat(child))
      ];

      return h('li', {
        staticClass: 'q-timeline__entry',
        class: this.classes,
        on: this.$listeners
      }, this.reverse === true ? content.reverse() : content)
    }
  });

  var QToolbar = Vue.extend({
    name: 'QToolbar',

    props: {
      inset: Boolean
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-toolbar row no-wrap items-center',
        class: this.inset ? 'q-toolbar--inset' : null,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QToolbarTitle = Vue.extend({
    name: 'QToolbarTitle',

    props: {
      shrink: Boolean
    },

    render: function render (h) {
      return h('div', {
        staticClass: 'q-toolbar__title ellipsis',
        class: this.shrink === true ? 'col-shrink' : null,
        on: this.$listeners
      }, slot(this, 'default'))
    }
  });

  var QTree = Vue.extend({
    name: 'QTree',

    mixins: [ DarkMixin ],

    props: {
      nodes: {
        type: Array,
        required: true
      },
      nodeKey: {
        type: String,
        required: true
      },
      labelKey: {
        type: String,
        default: 'label'
      },

      color: String,
      controlColor: String,
      textColor: String,
      selectedColor: String,

      icon: String,

      tickStrategy: {
        type: String,
        default: 'none',
        validator: function (v) { return ['none', 'strict', 'leaf', 'leaf-filtered'].includes(v); }
      },
      ticked: Array, // sync
      expanded: Array, // sync
      selected: {}, // sync

      defaultExpandAll: Boolean,
      accordion: Boolean,

      filter: String,
      filterMethod: {
        type: Function,
        default: function default$1 (node, filter) {
          var filt = filter.toLowerCase();
          return node[this.labelKey] &&
            node[this.labelKey].toLowerCase().indexOf(filt) > -1
        }
      },

      duration: Number,
      noConnectors: Boolean,

      noNodesLabel: String,
      noResultsLabel: String
    },

    computed: {
      classes: function classes () {
        return "q-tree" +
          (this.noConnectors === true ? " q-tree--no-connectors" : '') +
          (this.isDark === true ? " q-tree--dark" : '') +
          (this.color !== void 0 ? (" text-" + (this.color)) : '')
      },

      hasSelection: function hasSelection () {
        return this.selected !== void 0
      },

      computedIcon: function computedIcon () {
        return this.icon || this.$q.iconSet.tree.icon
      },

      computedControlColor: function computedControlColor () {
        return this.controlColor || this.color
      },

      textColorClass: function textColorClass () {
        if (this.textColor !== void 0) {
          return ("text-" + (this.textColor))
        }
      },

      selectedColorClass: function selectedColorClass () {
        var color = this.selectedColor || this.color;
        if (color) {
          return ("text-" + color)
        }
      },

      meta: function meta () {
        var this$1 = this;

        var meta = {};

        var travel = function (node, parent) {
          var tickStrategy = node.tickStrategy || (parent ? parent.tickStrategy : this$1.tickStrategy);
          var
            key = node[this$1.nodeKey],
            isParent = node.children && node.children.length > 0,
            isLeaf = isParent !== true,
            selectable = node.disabled !== true && this$1.hasSelection === true && node.selectable !== false,
            expandable = node.disabled !== true && node.expandable !== false,
            hasTicking = tickStrategy !== 'none',
            strictTicking = tickStrategy === 'strict',
            leafFilteredTicking = tickStrategy === 'leaf-filtered',
            leafTicking = tickStrategy === 'leaf' || tickStrategy === 'leaf-filtered';

          var tickable = node.disabled !== true && node.tickable !== false;
          if (leafTicking === true && tickable === true && parent && parent.tickable !== true) {
            tickable = false;
          }

          var lazy = node.lazy;
          if (lazy && this$1.lazy[key]) {
            lazy = this$1.lazy[key];
          }

          var m = {
            key: key,
            parent: parent,
            isParent: isParent,
            isLeaf: isLeaf,
            lazy: lazy,
            disabled: node.disabled,
            link: node.disabled !== true && (selectable === true || (expandable === true && (isParent === true || lazy === true))),
            children: [],
            matchesFilter: this$1.filter ? this$1.filterMethod(node, this$1.filter) : true,

            selected: key === this$1.selected && selectable === true,
            selectable: selectable,
            expanded: isParent === true ? this$1.innerExpanded.includes(key) : false,
            expandable: expandable,
            noTick: node.noTick === true || (strictTicking !== true && lazy && lazy !== 'loaded'),
            tickable: tickable,
            tickStrategy: tickStrategy,
            hasTicking: hasTicking,
            strictTicking: strictTicking,
            leafFilteredTicking: leafFilteredTicking,
            leafTicking: leafTicking,
            ticked: strictTicking === true
              ? this$1.innerTicked.includes(key)
              : (isLeaf === true ? this$1.innerTicked.includes(key) : false)
          };

          meta[key] = m;

          if (isParent === true) {
            m.children = node.children.map(function (n) { return travel(n, m); });

            if (this$1.filter) {
              if (m.matchesFilter !== true) {
                m.matchesFilter = m.children.some(function (n) { return n.matchesFilter; });
              }
              else if (
                m.noTick !== true &&
                m.disabled !== true &&
                m.tickable === true &&
                leafFilteredTicking === true &&
                m.children.every(function (n) { return n.matchesFilter !== true || n.noTick === true || n.tickable !== true; }) === true
              ) {
                m.tickable = false;
              }
            }

            if (m.matchesFilter === true) {
              if (m.noTick !== true && strictTicking !== true && m.children.every(function (n) { return n.noTick; }) === true) {
                m.noTick = true;
              }

              if (leafTicking) {
                m.ticked = false;
                m.indeterminate = m.children.some(function (node) { return node.indeterminate === true; });
                m.tickable = m.tickable === true && m.children.some(function (node) { return node.tickable; });

                if (m.indeterminate !== true) {
                  var sel = m.children
                    .reduce(function (acc, meta) { return meta.ticked === true ? acc + 1 : acc; }, 0);

                  if (sel === m.children.length) {
                    m.ticked = true;
                  }
                  else if (sel > 0) {
                    m.indeterminate = true;
                  }
                }

                if (m.indeterminate === true) {
                  m.indeterminateNextState = m.children
                    .every(function (meta) { return meta.tickable !== true || meta.ticked !== true; });
                }
              }
            }
          }

          return m
        };

        this.nodes.forEach(function (node) { return travel(node, null); });
        return meta
      }
    },

    data: function data () {
      return {
        lazy: {},
        innerTicked: this.ticked || [],
        innerExpanded: this.expanded || []
      }
    },

    watch: {
      ticked: function ticked (val) {
        this.innerTicked = val;
      },

      expanded: function expanded (val) {
        this.innerExpanded = val;
      }
    },

    methods: {
      getNodeByKey: function getNodeByKey (key) {
        var this$1 = this;

        var reduce = [].reduce;

        var find = function (result, node) {
          if (result || !node) {
            return result
          }
          if (Array.isArray(node) === true) {
            return reduce.call(Object(node), find, result)
          }
          if (node[this$1.nodeKey] === key) {
            return node
          }
          if (node.children) {
            return find(null, node.children)
          }
        };

        return find(null, this.nodes)
      },

      getTickedNodes: function getTickedNodes () {
        var this$1 = this;

        return this.innerTicked.map(function (key) { return this$1.getNodeByKey(key); })
      },

      getExpandedNodes: function getExpandedNodes () {
        var this$1 = this;

        return this.innerExpanded.map(function (key) { return this$1.getNodeByKey(key); })
      },

      isExpanded: function isExpanded (key) {
        return key && this.meta[key]
          ? this.meta[key].expanded
          : false
      },

      collapseAll: function collapseAll () {
        if (this.expanded !== void 0) {
          this.$emit('update:expanded', []);
        }
        else {
          this.innerExpanded = [];
        }
      },

      expandAll: function expandAll () {
        var this$1 = this;

        var
          expanded = this.innerExpanded,
          travel = function (node) {
            if (node.children && node.children.length > 0) {
              if (node.expandable !== false && node.disabled !== true) {
                expanded.push(node[this$1.nodeKey]);
                node.children.forEach(travel);
              }
            }
          };

        this.nodes.forEach(travel);

        if (this.expanded !== void 0) {
          this.$emit('update:expanded', expanded);
        }
        else {
          this.innerExpanded = expanded;
        }
      },

      setExpanded: function setExpanded (key, state, node, meta) {
        var this$1 = this;
        if ( node === void 0 ) node = this.getNodeByKey(key);
        if ( meta === void 0 ) meta = this.meta[key];

        if (meta.lazy && meta.lazy !== 'loaded') {
          if (meta.lazy === 'loading') {
            return
          }

          this.$set(this.lazy, key, 'loading');
          this.$emit('lazy-load', {
            node: node,
            key: key,
            done: function (children) {
              this$1.lazy[key] = 'loaded';
              if (children) {
                this$1.$set(node, 'children', children);
              }
              this$1.$nextTick(function () {
                var m = this$1.meta[key];
                if (m && m.isParent === true) {
                  this$1.__setExpanded(key, true);
                }
              });
            },
            fail: function () {
              this$1.$delete(this$1.lazy, key);
            }
          });
        }
        else if (meta.isParent === true && meta.expandable === true) {
          this.__setExpanded(key, state);
        }
      },

      __setExpanded: function __setExpanded (key, state) {
        var this$1 = this;

        var target = this.innerExpanded;
        var emit = this.expanded !== void 0;

        if (emit === true) {
          target = target.slice();
        }

        if (state) {
          if (this.accordion) {
            if (this.meta[key]) {
              var collapse = [];
              if (this.meta[key].parent) {
                this.meta[key].parent.children.forEach(function (m) {
                  if (m.key !== key && m.expandable === true) {
                    collapse.push(m.key);
                  }
                });
              }
              else {
                this.nodes.forEach(function (node) {
                  var k = node[this$1.nodeKey];
                  if (k !== key) {
                    collapse.push(k);
                  }
                });
              }
              if (collapse.length > 0) {
                target = target.filter(function (k) { return collapse.includes(k) === false; });
              }
            }
          }

          target = target.concat([ key ])
            .filter(function (key, index, self) { return self.indexOf(key) === index; });
        }
        else {
          target = target.filter(function (k) { return k !== key; });
        }

        if (emit === true) {
          this.$emit("update:expanded", target);
        }
        else {
          this.innerExpanded = target;
        }
      },

      isTicked: function isTicked (key) {
        return key && this.meta[key]
          ? this.meta[key].ticked
          : false
      },

      setTicked: function setTicked (keys, state) {
        var target = this.innerTicked;
        var emit = this.ticked !== void 0;

        if (emit === true) {
          target = target.slice();
        }

        if (state) {
          target = target.concat(keys)
            .filter(function (key, index, self) { return self.indexOf(key) === index; });
        }
        else {
          target = target.filter(function (k) { return keys.includes(k) === false; });
        }

        if (emit === true) {
          this.$emit("update:ticked", target);
        }
      },

      __getSlotScope: function __getSlotScope (node, meta, key) {
        var this$1 = this;

        var scope = { tree: this, node: node, key: key, color: this.color, dark: this.isDark };

        Object.defineProperty(scope, 'expanded', {
          get: function () { return meta.expanded },
          set: function (val) { val !== meta.expanded && this$1.setExpanded(key, val); },
          configurable: true,
          enumerable: true
        });
        Object.defineProperty(scope, 'ticked', {
          get: function () { return meta.ticked },
          set: function (val) { val !== meta.ticked && this$1.setTicked([ key ], val); },
          configurable: true,
          enumerable: true
        });

        return scope
      },

      __getChildren: function __getChildren (h, nodes) {
        var this$1 = this;

        return (
          this.filter
            ? nodes.filter(function (n) { return this$1.meta[n[this$1.nodeKey]].matchesFilter; })
            : nodes
        ).map(function (child) { return this$1.__getNode(h, child); })
      },

      __getNodeMedia: function __getNodeMedia (h, node) {
        if (node.icon !== void 0) {
          return h(QIcon, {
            staticClass: "q-tree__icon q-mr-sm",
            props: { name: node.icon, color: node.iconColor }
          })
        }
        var src = node.img || node.avatar;
        if (src) {
          return h('img', {
            staticClass: ("q-tree__" + (node.img ? 'img' : 'avatar') + " q-mr-sm"),
            attrs: { src: src }
          })
        }
      },

      __getNode: function __getNode (h, node) {
        var this$1 = this;

        var
          key = node[this.nodeKey],
          meta = this.meta[key],
          header = node.header
            ? this.$scopedSlots[("header-" + (node.header))] || this.$scopedSlots['default-header']
            : this.$scopedSlots['default-header'];

        var children = meta.isParent === true
          ? this.__getChildren(h, node.children)
          : [];

        var isParent = children.length > 0 || (meta.lazy && meta.lazy !== 'loaded');

        var
          body = node.body
            ? this.$scopedSlots[("body-" + (node.body))] || this.$scopedSlots['default-body']
            : this.$scopedSlots['default-body'],
          slotScope = header !== void 0 || body !== void 0
            ? this.__getSlotScope(node, meta, key)
            : null;

        if (body !== void 0) {
          body = h('div', { staticClass: 'q-tree__node-body relative-position' }, [
            h('div', { class: this.textColorClass }, [
              body(slotScope)
            ])
          ]);
        }

        return h('div', {
          key: key,
          staticClass: 'q-tree__node relative-position',
          class: { 'q-tree__node--parent': isParent, 'q-tree__node--child': !isParent }
        }, [
          h('div', {
            staticClass: 'q-tree__node-header relative-position row no-wrap items-center',
            class: {
              'q-tree__node--link q-hoverable q-focusable': meta.link,
              'q-tree__node--selected': meta.selected,
              'q-tree__node--disabled': meta.disabled
            },
            attrs: { tabindex: meta.link ? 0 : -1 },
            on: {
              click: function (e) {
                this$1.__onClick(node, meta, e);
              },
              keypress: function (e) {
                if (shouldIgnoreKey(e) !== true) {
                  if (e.keyCode === 13) { this$1.__onClick(node, meta, e, true); }
                  else if (e.keyCode === 32) { this$1.__onExpandClick(node, meta, e, true); }
                }
              }
            }
          }, [
            h('div', { staticClass: 'q-focus-helper', attrs: { tabindex: -1 }, ref: ("blurTarget_" + (meta.key)) }),

            meta.lazy === 'loading'
              ? h(QSpinner, {
                staticClass: 'q-tree__spinner q-mr-xs',
                props: { color: this.computedControlColor }
              })
              : (
                isParent === true
                  ? h(QIcon, {
                    staticClass: 'q-tree__arrow q-mr-xs',
                    class: { 'q-tree__arrow--rotate': meta.expanded },
                    props: { name: this.computedIcon },
                    nativeOn: {
                      click: function (e) {
                        this$1.__onExpandClick(node, meta, e);
                      }
                    }
                  })
                  : null
              ),

            meta.hasTicking === true && meta.noTick !== true
              ? h(QCheckbox, {
                staticClass: 'q-mr-xs',
                props: {
                  value: meta.indeterminate === true ? null : meta.ticked,
                  color: this.computedControlColor,
                  dark: this.isDark,
                  dense: true,
                  keepColor: true,
                  disable: meta.tickable !== true
                },
                on: {
                  keydown: stopAndPrevent,
                  input: function (v) {
                    this$1.__onTickedClick(meta, v);
                  }
                }
              })
              : null,

            h('div', {
              'staticClass': 'q-tree__node-header-content col row no-wrap items-center',
              class: meta.selected ? this.selectedColorClass : this.textColorClass
            }, [
              header
                ? header(slotScope)
                : [
                  this.__getNodeMedia(h, node),
                  h('div', node[this.labelKey])
                ]
            ])
          ]),

          isParent === true
            ? h(QSlideTransition, {
              props: { duration: this.duration },
              on: cache(this, 'slide', {
                show: function () { this$1.$emit('after-show'); },
                hide: function () { this$1.$emit('after-hide'); }
              })
            }, [
              h('div', {
                staticClass: 'q-tree__node-collapsible',
                class: this.textColorClass,
                directives: [{ name: 'show', value: meta.expanded }]
              }, [
                body,

                h('div', {
                  staticClass: 'q-tree__children',
                  class: { 'q-tree__node--disabled': meta.disabled }
                }, children)
              ])
            ])
            : body
        ])
      },

      __blur: function __blur (key) {
        var blurTarget = this.$refs[("blurTarget_" + key)];
        blurTarget !== void 0 && blurTarget.focus();
      },

      __onClick: function __onClick (node, meta, e, keyboard) {
        keyboard !== true && this.__blur(meta.key);

        if (this.hasSelection) {
          if (meta.selectable) {
            this.$emit('update:selected', meta.key !== this.selected ? meta.key : null);
          }
        }
        else {
          this.__onExpandClick(node, meta, e, keyboard);
        }

        if (typeof node.handler === 'function') {
          node.handler(node);
        }
      },

      __onExpandClick: function __onExpandClick (node, meta, e, keyboard) {
        if (e !== void 0) {
          stopAndPrevent(e);
        }
        keyboard !== true && this.__blur(meta.key);
        this.setExpanded(meta.key, !meta.expanded, node, meta);
      },

      __onTickedClick: function __onTickedClick (meta, state) {
        if (meta.indeterminate === true) {
          state = meta.indeterminateNextState;
        }
        if (meta.strictTicking) {
          this.setTicked([ meta.key ], state);
        }
        else if (meta.leafTicking) {
          var keys = [];
          var travel = function (meta) {
            if (meta.isParent) {
              if (state !== true && meta.noTick !== true && meta.tickable === true) {
                keys.push(meta.key);
              }
              if (meta.leafTicking === true) {
                meta.children.forEach(travel);
              }
            }
            else if (
              meta.noTick !== true &&
              meta.tickable === true &&
              (meta.leafFilteredTicking !== true || meta.matchesFilter === true)
            ) {
              keys.push(meta.key);
            }
          };
          travel(meta);
          this.setTicked(keys, state);
        }
      }
    },

    render: function render (h) {
      var children = this.__getChildren(h, this.nodes);

      return h(
        'div', {
          class: this.classes
        },
        children.length === 0
          ? (
            this.filter
              ? this.noResultsLabel || this.$q.lang.tree.noResults
              : this.noNodesLabel || this.$q.lang.tree.noNodes
          )
          : children
      )
    },

    created: function created () {
      this.defaultExpandAll === true && this.expandAll();
    }
  });

  var QUploaderBase = Vue.extend({
    name: 'QUploaderBase',

    mixins: [ DarkMixin, FileMixin ],

    props: {
      label: String,

      color: String,
      textColor: String,

      square: Boolean,
      flat: Boolean,
      bordered: Boolean,

      noThumbnails: Boolean,
      autoUpload: Boolean,
      hideUploadBtn: Boolean,

      disable: Boolean,
      readonly: Boolean
    },

    provide: function provide () {
      return {
        __qUploaderGetInput: this.__getInputControl
      }
    },

    data: function data () {
      return {
        files: [],
        queuedFiles: [],
        uploadedFiles: [],
        dnd: false,
        expanded: false,

        uploadSize: 0,
        uploadedSize: 0
      }
    },

    watch: {
      isUploading: function isUploading (newVal, oldVal) {
        if (oldVal === false && newVal === true) {
          this.$emit('start');
        }
        else if (oldVal === true && newVal === false) {
          this.$emit('finish');
        }
      }
    },

    computed: {
      /*
       * When extending:
       *   Required : isUploading
       *   Optional: isBusy
       */

      canUpload: function canUpload () {
        return this.editable === true &&
          this.isBusy !== true &&
          this.isUploading !== true &&
          this.queuedFiles.length > 0
      },

      canAddFiles: function canAddFiles () {
        return this.editable &&
          this.isUploading !== true &&
          (this.multiple === true || this.queuedFiles.length === 0)
      },

      extensions: function extensions () {
        if (this.accept !== void 0) {
          return this.accept.split(',').map(function (ext) {
            ext = ext.trim();
            // support "image/*"
            if (ext.endsWith('/*')) {
              ext = ext.slice(0, ext.length - 1);
            }
            return ext
          })
        }
      },

      uploadProgress: function uploadProgress () {
        return this.uploadSize === 0
          ? 0
          : this.uploadedSize / this.uploadSize
      },

      uploadProgressLabel: function uploadProgressLabel () {
        return this.__getProgressLabel(this.uploadProgress)
      },

      uploadedSizeLabel: function uploadedSizeLabel () {
        return humanStorageSize(this.uploadedSize)
      },

      uploadSizeLabel: function uploadSizeLabel () {
        return humanStorageSize(this.uploadSize)
      },

      colorClass: function colorClass () {
        var cls = [];
        this.color !== void 0 && cls.push(("bg-" + (this.color)));
        this.textColor !== void 0 && cls.push(("text-" + (this.textColor)));
        return cls.join(' ')
      },

      editable: function editable () {
        return this.disable !== true && this.readonly !== true
      }
    },

    methods: {
      reset: function reset () {
        if (!this.disable) {
          this.abort();
          this.uploadedSize = 0;
          this.uploadSize = 0;
          this.__revokeImgURLs();
          this.files = [];
          this.queuedFiles = [];
          this.uploadedFiles = [];
        }
      },

      removeUploadedFiles: function removeUploadedFiles () {
        if (!this.disable) {
          this.files = this.files.filter(function (f) {
            if (f.__status !== 'uploaded') {
              return true
            }

            f._img !== void 0 && window.URL.revokeObjectURL(f._img.src);

            return false
          });
          this.uploadedFiles = [];
        }
      },

      removeQueuedFiles: function removeQueuedFiles () {
        var this$1 = this;

        if (!this.disable) {
          var removedFiles = [];

          var files = this.files.filter(function (f) {
            if (f.__status !== 'idle' && f.__status !== 'failed') {
              return true
            }

            this$1.uploadSize -= f.size;
            removedFiles.push(f);

            f._img !== void 0 && window.URL.revokeObjectURL(f._img.src);

            return false
          });

          if (removedFiles.length > 0) {
            this.files = files;
            this.queuedFiles = [];
            this.$emit('removed', removedFiles);
          }
        }
      },

      removeFile: function removeFile (file) {
        if (this.disable) { return }

        if (file.__status === 'uploaded') {
          this.uploadedFiles = this.uploadedFiles.filter(function (f) { return f.name !== file.name; });
        }
        else if (file.__status === 'uploading') {
          file.__abort();
        }
        else {
          this.uploadSize -= file.size;
        }

        this.files = this.files.filter(function (f) {
          if (f.name !== file.name) {
            return true
          }

          f._img !== void 0 && window.URL.revokeObjectURL(f._img.src);

          return false
        });
        this.queuedFiles = this.queuedFiles.filter(function (f) { return f.name !== file.name; });
        this.$emit('removed', [ file ]);
      },

      __revokeImgURLs: function __revokeImgURLs () {
        this.files.forEach(function (f) {
          f._img !== void 0 && window.URL.revokeObjectURL(f._img.src);
        });
      },

      __getFileInput: function __getFileInput () {
        return this.$refs.input ||
          this.$el.getElementsByClassName('q-uploader__input')[0]
      },

      __getProgressLabel: function __getProgressLabel (p) {
        return (p * 100).toFixed(2) + '%'
      },

      __updateFile: function __updateFile (file, status, uploadedSize) {
        file.__status = status;

        if (status === 'idle') {
          file.__uploaded = 0;
          file.__progress = 0;
          file.__sizeLabel = humanStorageSize(file.size);
          file.__progressLabel = '0.00%';
          return
        }
        if (status === 'failed') {
          this.$forceUpdate();
          return
        }

        file.__uploaded = status === 'uploaded'
          ? file.size
          : uploadedSize;

        file.__progress = status === 'uploaded'
          ? 1
          : Math.min(0.9999, file.__uploaded / file.size);

        file.__progressLabel = this.__getProgressLabel(file.__progress);
        this.$forceUpdate();
      },

      __addFiles: function __addFiles (e, fileList) {
        var this$1 = this;

        var files = this.__processFiles(e, fileList);
        this.__getFileInput().value = '';

        if (files === void 0) { return }

        files.forEach(function (file) {
          this$1.__updateFile(file, 'idle');
          this$1.uploadSize += file.size;

          if (this$1.noThumbnails !== true && file.type.toUpperCase().startsWith('IMAGE')) {
            var img = new Image();
            img.src = window.URL.createObjectURL(file);
            file.__img = img;
          }
        });

        this.files = this.files.concat(files);
        this.queuedFiles = this.queuedFiles.concat(files);
        this.$emit('added', files);
        this.autoUpload === true && this.upload();
      },

      __getBtn: function __getBtn (h, show, icon, fn) {
        if (show === true) {
          return h(QBtn, {
            props: {
              type: 'a',
              icon: this.$q.iconSet.uploader[icon],
              flat: true,
              dense: true
            },
            on: icon === 'add' ? null : { click: fn }
          }, icon === 'add' ? this.__getInputControl(h) : null)
        }
      },

      __getInputControl: function __getInputControl (h) {
        return [
          h('input', {
            ref: 'input',
            staticClass: 'q-uploader__input overflow-hidden absolute-full',
            attrs: Object.assign({}, {tabindex: -1,
              type: 'file',
              title: '', // try to remove default tooltip
              accept: this.accept},
              (this.multiple === true ? { multiple: true } : {})),
            on: cache(this, 'input', {
              mousedown: stop, // need to stop refocus from QBtn
              change: this.__addFiles
            })
          })
        ]
      },

      __getHeader: function __getHeader (h) {
        if (this.$scopedSlots.header !== void 0) {
          return this.$scopedSlots.header(this)
        }

        return [
          h('div', {
            staticClass: 'q-uploader__header-content flex flex-center no-wrap q-gutter-xs'
          }, [
            this.__getBtn(h, this.queuedFiles.length > 0, 'removeQueue', this.removeQueuedFiles),
            this.__getBtn(h, this.uploadedFiles.length > 0, 'removeUploaded', this.removeUploadedFiles),

            this.isUploading === true
              ? h(QSpinner, { staticClass: 'q-uploader__spinner' })
              : null,

            h('div', { staticClass: 'col column justify-center' }, [
              this.label !== void 0
                ? h('div', { staticClass: 'q-uploader__title' }, [ this.label ])
                : null,

              h('div', { staticClass: 'q-uploader__subtitle' }, [
                this.uploadSizeLabel + ' / ' + this.uploadProgressLabel
              ])
            ]),

            this.__getBtn(h, this.canAddFiles, 'add', this.pickFiles),
            this.__getBtn(h, this.hideUploadBtn === false && this.canUpload === true, 'upload', this.upload),
            this.__getBtn(h, this.isUploading, 'clear', this.abort)
          ])
        ]
      },

      __getList: function __getList (h) {
        var this$1 = this;

        if (this.$scopedSlots.list !== void 0) {
          return this.$scopedSlots.list(this)
        }

        return this.files.map(function (file) { return h('div', {
          key: file.name,
          staticClass: 'q-uploader__file relative-position',
          class: {
            'q-uploader__file--img': this$1.noThumbnails !== true && file.__img !== void 0,
            'q-uploader__file--failed': file.__status === 'failed',
            'q-uploader__file--uploaded': file.__status === 'uploaded'
          },
          style: this$1.noThumbnails !== true && file.__img !== void 0 ? {
            backgroundImage: 'url(' + file.__img.src + ')'
          } : null
        }, [
          h('div', {
            staticClass: 'q-uploader__file-header row flex-center no-wrap'
          }, [
            file.__status === 'failed'
              ? h(QIcon, {
                staticClass: 'q-uploader__file-status',
                props: {
                  name: this$1.$q.iconSet.type.negative,
                  color: 'negative'
                }
              })
              : null,

            h('div', { staticClass: 'q-uploader__file-header-content col' }, [
              h('div', { staticClass: 'q-uploader__title' }, [ file.name ]),
              h('div', {
                staticClass: 'q-uploader__subtitle row items-center no-wrap'
              }, [
                file.__sizeLabel + ' / ' + file.__progressLabel
              ])
            ]),

            file.__status === 'uploading'
              ? h(QCircularProgress, {
                props: {
                  value: file.__progress,
                  min: 0,
                  max: 1,
                  indeterminate: file.__progress === 0
                }
              })
              : h(QBtn, {
                props: {
                  round: true,
                  dense: true,
                  flat: true,
                  icon: this$1.$q.iconSet.uploader[file.__status === 'uploaded' ? 'done' : 'clear']
                },
                on: {
                  click: function () { this$1.removeFile(file); }
                }
              })
          ])
        ]); })
      }
    },

    beforeDestroy: function beforeDestroy () {
      this.isUploading === true && this.abort();
      this.files.length > 0 && this.__revokeImgURLs();
    },

    render: function render (h) {
      var children = [
        h('div', {
          staticClass: 'q-uploader__header',
          class: this.colorClass
        }, this.__getHeader(h)),

        h('div', {
          staticClass: 'q-uploader__list scroll'
        }, this.__getList(h)),

        this.__getDnd(h, 'uploader')
      ];

      this.isBusy === true && children.push(
        h('div', {
          staticClass: 'q-uploader__overlay absolute-full flex flex-center'
        }, [ h(QSpinner) ])
      );

      return h('div', {
        staticClass: 'q-uploader column no-wrap',
        class: {
          'q-uploader--dark q-dark': this.isDark,
          'q-uploader--bordered': this.bordered,
          'q-uploader--square no-border-radius': this.square,
          'q-uploader--flat no-shadow': this.flat,
          'disabled q-uploader--disable': this.disable
        },
        on: this.canAddFiles === true
          ? cache(this, 'drag', { dragover: this.__onDragOver })
          : null
      }, children)
    }
  });

  function getFn (prop) {
    return typeof prop === 'function'
      ? prop
      : function () { return prop; }
  }

  var UploaderXHRMixin = {
    props: {
      url: [Function, String],
      method: {
        type: [Function, String],
        default: 'POST'
      },
      fieldName: {
        type: [Function, String],
        default: function (file) { return file.name; }
      },
      headers: [Function, Array],
      formFields: [Function, Array],
      withCredentials: [Function, Boolean],
      sendRaw: [Function, Boolean],

      batch: [Function, Boolean],
      factory: Function
    },

    data: function data () {
      return {
        xhrs: [],
        promises: [],
        workingThreads: 0
      }
    },

    computed: {
      xhrProps: function xhrProps () {
        return {
          url: getFn(this.url),
          method: getFn(this.method),
          headers: getFn(this.headers),
          formFields: getFn(this.formFields),
          fieldName: getFn(this.fieldName),
          withCredentials: getFn(this.withCredentials),
          sendRaw: getFn(this.sendRaw),
          batch: getFn(this.batch)
        }
      },

      isUploading: function isUploading () {
        return this.workingThreads > 0
      },

      isBusy: function isBusy () {
        return this.promises.length > 0
      }
    },

    methods: {
      abort: function abort () {
        this.xhrs.forEach(function (x) { x.abort(); });

        if (this.promises.length > 0) {
          this.abortPromises = true;
        }
      },

      upload: function upload () {
        var this$1 = this;

        if (this.canUpload === false) {
          return
        }

        var queue = this.queuedFiles.slice(0);
        this.queuedFiles = [];

        if (this.xhrProps.batch(queue)) {
          this.__runFactory(queue);
        }
        else {
          queue.forEach(function (file) {
            this$1.__runFactory([ file ]);
          });
        }
      },

      __runFactory: function __runFactory (files) {
        var this$1 = this;

        this.workingThreads++;

        if (typeof this.factory !== 'function') {
          this.__uploadFiles(files, {});
          return
        }

        var res = this.factory(files);

        if (!res) {
          this.$emit(
            'factory-failed',
            new Error('QUploader: factory() does not return properly'),
            files
          );
          this.workingThreads--;
        }
        else if (typeof res.catch === 'function' && typeof res.then === 'function') {
          this.promises.push(res);

          var failed = function (err) {
            if (this$1._isBeingDestroyed !== true && this$1._isDestroyed !== true) {
              this$1.promises = this$1.promises.filter(function (p) { return p !== res; });

              if (this$1.promises.length === 0) {
                this$1.abortPromises = false;
              }

              this$1.queuedFiles = this$1.queuedFiles.concat(files);
              files.forEach(function (f) { this$1.__updateFile(f, 'failed'); });

              this$1.$emit('factory-failed', err, files);
              this$1.workingThreads--;
            }
          };

          res.then(function (factory) {
            if (this$1.abortPromises === true) {
              failed(new Error('Aborted'));
            }
            else if (this$1._isBeingDestroyed !== true && this$1._isDestroyed !== true) {
              this$1.promises = this$1.promises.filter(function (p) { return p !== res; });
              this$1.__uploadFiles(files, factory);
            }
          }).catch(failed);
        }
        else {
          this.__uploadFiles(files, res || {});
        }
      },

      __uploadFiles: function __uploadFiles (files, factory) {
        var this$1 = this;

        var
          form = new FormData(),
          xhr = new XMLHttpRequest();

        var getProp = function (name, arg) {
          return factory[name] !== void 0
            ? getFn(factory[name])(arg)
            : this$1.xhrProps[name](arg)
        };

        var url = getProp('url', files);

        if (!url) {
          console.error('q-uploader: invalid or no URL specified');
          this.workingThreads--;
          return
        }

        var fields = getProp('formFields', files);
        fields !== void 0 && fields.forEach(function (field) {
          form.append(field.name, field.value);
        });

        var
          uploadIndex = 0,
          uploadIndexSize = 0,
          uploadedSize = 0,
          maxUploadSize = 0,
          aborted;

        xhr.upload.addEventListener('progress', function (e) {
          if (aborted === true) { return }

          var loaded = Math.min(maxUploadSize, e.loaded);

          this$1.uploadedSize += loaded - uploadedSize;
          uploadedSize = loaded;

          var size = uploadedSize - uploadIndexSize;
          for (var i = uploadIndex; size > 0 && i < files.length; i++) {
            var
              file = files[i],
              uploaded = size > file.size;

            if (uploaded) {
              size -= file.size;
              uploadIndex++;
              uploadIndexSize += file.size;
              this$1.__updateFile(file, 'uploading', file.size);
            }
            else {
              this$1.__updateFile(file, 'uploading', size);
              return
            }
          }
        }, false);

        xhr.onreadystatechange = function () {
          if (xhr.readyState < 4) {
            return
          }

          if (xhr.status && xhr.status < 400) {
            this$1.uploadedFiles = this$1.uploadedFiles.concat(files);
            files.forEach(function (f) { this$1.__updateFile(f, 'uploaded'); });
            this$1.$emit('uploaded', { files: files, xhr: xhr });
          }
          else {
            aborted = true;
            this$1.uploadedSize -= uploadedSize;
            this$1.queuedFiles = this$1.queuedFiles.concat(files);
            files.forEach(function (f) { this$1.__updateFile(f, 'failed'); });
            this$1.$emit('failed', { files: files, xhr: xhr });
          }

          this$1.workingThreads--;
          this$1.xhrs = this$1.xhrs.filter(function (x) { return x !== xhr; });
        };

        xhr.open(
          getProp('method', files),
          url
        );

        if (getProp('withCredentials', files) === true) {
          xhr.withCredentials = true;
        }

        var headers = getProp('headers', files);
        headers !== void 0 && headers.forEach(function (head) {
          xhr.setRequestHeader(head.name, head.value);
        });

        var sendRaw = getProp('sendRaw', files);

        files.forEach(function (file) {
          this$1.__updateFile(file, 'uploading', 0);
          if (sendRaw !== true) {
            form.append(getProp('fieldName', file), file, file.name);
          }
          file.xhr = xhr;
          file.__abort = function () { xhr.abort(); };
          maxUploadSize += file.size;
        });

        this.$emit('uploading', { files: files, xhr: xhr });
        this.xhrs.push(xhr);

        if (sendRaw === true) {
          xhr.send(new Blob(files));
        }
        else {
          xhr.send(form);
        }
      }
    }
  };

  var QUploader = Vue.extend({
    name: 'QUploader',
    mixins: [ QUploaderBase, UploaderXHRMixin ]
  });

  var QUploaderAddTrigger = Vue.extend({
    name: 'QUploaderAddTrigger',

    inject: {
      __qUploaderGetInput: {
        default: function default$1 () {
          console.error('QUploaderAddTrigger needs to be child of QUploader');
        }
      }
    },

    render: function render (h) {
      return this.__qUploaderGetInput(h)
    }
  });

  var QVideo = Vue.extend({
    name: 'QVideo',

    mixins: [ RatioMixin ],

    props: {
      src: {
        type: String,
        required: true
      }
    },

    computed: {
      iframeData: function iframeData () {
        return {
          attrs: {
            src: this.src,
            frameborder: '0',
            allowfullscreen: true
          }
        }
      },

      classes: function classes () {
        return 'q-video' +
          (this.ratio !== void 0 ? ' q-video--responsive' : '')
      }
    },

    render: function render (h) {
      return h('div', {
        class: this.classes,
        style: this.ratioStyle,
        on: this.$listeners
      }, [
        h('iframe', this.iframeData)
      ])
    }
  });



  var components$1 = /*#__PURE__*/Object.freeze({
    __proto__: null,
    QAjaxBar: QAjaxBar,
    QAvatar: QAvatar,
    QBadge: QBadge,
    QBanner: QBanner,
    QBar: QBar,
    QBreadcrumbs: QBreadcrumbs,
    QBreadcrumbsEl: QBreadcrumbsEl,
    QBtn: QBtn,
    QBtnDropdown: QBtnDropdown,
    QBtnGroup: QBtnGroup,
    QBtnToggle: QBtnToggle,
    QCard: QCard,
    QCardSection: QCardSection,
    QCardActions: QCardActions,
    QCarousel: QCarousel,
    QCarouselSlide: QCarouselSlide,
    QCarouselControl: QCarouselControl,
    QChatMessage: QChatMessage,
    QCheckbox: QCheckbox,
    QChip: QChip,
    QCircularProgress: QCircularProgress,
    QColor: QColor,
    QDate: QDate,
    QDialog: QDialog,
    QDrawer: QDrawer,
    QEditor: QEditor,
    QExpansionItem: QExpansionItem,
    QFab: QFab,
    QFabAction: QFabAction,
    QField: QField,
    QFile: QFile,
    QFooter: QFooter,
    QForm: QForm,
    QHeader: QHeader,
    QIcon: QIcon,
    QImg: QImg,
    QInfiniteScroll: QInfiniteScroll,
    QInnerLoading: QInnerLoading,
    QInput: QInput,
    QIntersection: QIntersection,
    QList: QList,
    QItem: QItem,
    QItemSection: QItemSection,
    QItemLabel: QItemLabel,
    QKnob: QKnob,
    QLayout: QLayout,
    QMarkupTable: QMarkupTable,
    QMenu: QMenu,
    QNoSsr: QNoSsr,
    QOptionGroup: QOptionGroup,
    QPage: QPage,
    QPageContainer: QPageContainer,
    QPageScroller: QPageScroller,
    QPageSticky: QPageSticky,
    QPagination: QPagination,
    QParallax: QParallax,
    QPopupEdit: QPopupEdit,
    QPopupProxy: QPopupProxy,
    QLinearProgress: QLinearProgress,
    QPullToRefresh: QPullToRefresh,
    QRadio: QRadio,
    QRange: QRange,
    QRating: QRating,
    QResizeObserver: QResizeObserver,
    QResponsive: QResponsive,
    QScrollArea: QScrollArea,
    QScrollObserver: QScrollObserver,
    QSelect: QSelect,
    QSeparator: QSeparator,
    QSkeleton: QSkeleton,
    QSlideItem: QSlideItem,
    QSlideTransition: QSlideTransition,
    QSlider: QSlider,
    QSpace: QSpace,
    QSpinner: QSpinner,
    QSpinnerAudio: QSpinnerAudio,
    QSpinnerBall: QSpinnerBall,
    QSpinnerBars: QSpinnerBars,
    QSpinnerComment: QSpinnerComment,
    QSpinnerCube: QSpinnerCube,
    QSpinnerDots: QSpinnerDots,
    QSpinnerFacebook: QSpinnerFacebook,
    QSpinnerGears: QSpinnerGears,
    QSpinnerGrid: QSpinnerGrid,
    QSpinnerHearts: QSpinnerHearts,
    QSpinnerHourglass: QSpinnerHourglass,
    QSpinnerInfinity: QSpinnerInfinity,
    QSpinnerIos: QSpinnerIos,
    QSpinnerOval: QSpinnerOval,
    QSpinnerPie: QSpinnerPie,
    QSpinnerPuff: QSpinnerPuff,
    QSpinnerRadio: QSpinnerRadio,
    QSpinnerRings: QSpinnerRings,
    QSpinnerTail: QSpinnerTail,
    QSplitter: QSplitter,
    QStep: QStep,
    QStepper: QStepper,
    QStepperNavigation: QStepperNavigation,
    QTabPanels: QTabPanels,
    QTabPanel: QTabPanel,
    QTable: QTable,
    QTh: QTh,
    QTr: QTr,
    QTd: QTd,
    QTabs: QTabs,
    QTab: QTab,
    QRouteTab: QRouteTab,
    QTime: QTime,
    QTimeline: QTimeline,
    QTimelineEntry: QTimelineEntry,
    QToggle: QToggle,
    QToolbar: QToolbar,
    QToolbarTitle: QToolbarTitle,
    QTooltip: QTooltip,
    QTree: QTree,
    QUploader: QUploader,
    QUploaderBase: QUploaderBase,
    QUploaderAddTrigger: QUploaderAddTrigger,
    QVideo: QVideo,
    QVirtualScroll: QVirtualScroll
  });

  /*
   * depth
   *   < 0  --> close all chain
   *   0    --> disabled
   *   > 0  --> close chain up to N parent
   */

  function getDepth (value) {
    if (value === false) {
      return 0
    }
    if (value === true || value === void 0) {
      return 1
    }

    var depth = parseInt(value, 10);
    return isNaN(depth) ? 0 : depth
  }

  var ClosePopup = {
    name: 'close-popup',

    bind: function bind (el, ref, vnode) {
      var value = ref.value;

      var ctx = {
        depth: getDepth(value),

        handler: function handler (evt) {
          // allow @click to be emitted
          ctx.depth !== 0 && setTimeout(function () {
            closePortals(vnode.componentInstance || vnode.context, evt, ctx.depth);
          });
        },

        handlerKey: function handlerKey (evt) {
          isKeyCode(evt, 13) === true && ctx.handler(evt);
        }
      };

      if (el.__qclosepopup !== void 0) {
        el.__qclosepopup_old = el.__qclosepopup;
      }

      el.__qclosepopup = ctx;

      el.addEventListener('click', ctx.handler);
      el.addEventListener('keyup', ctx.handlerKey);
    },

    update: function update (el, ref) {
      var value = ref.value;
      var oldValue = ref.oldValue;

      if (el.__qclosepopup !== void 0 && value !== oldValue) {
        el.__qclosepopup.depth = getDepth(value);
      }
    },

    unbind: function unbind (el) {
      var ctx = el.__qclosepopup_old || el.__qclosepopup;
      if (ctx !== void 0) {
        el.removeEventListener('click', ctx.handler);
        el.removeEventListener('keyup', ctx.handlerKey);
        delete el[el.__qclosepopup_old ? '__qclosepopup_old' : '__qclosepopup'];
      }
    }
  };

  var GoBack = {
    name: 'go-back',

    bind: function bind (el, ref, vnode) {
      var value = ref.value;
      var modifiers = ref.modifiers;

      var ctx = {
        value: value,

        position: window.history.length - 1,
        single: modifiers.single,

        goBack: function goBack () {
          var router = vnode.context.$router;

          if (ctx.single === true) {
            router.go(-1);
          }
          else if (client.is.nativeMobile === true) {
            router.go(ctx.position - window.history.length);
          }
          else {
            router.replace(ctx.value);
          }
        },

        goBackKey: function goBackKey (e) {
          // if ENTER key
          isKeyCode(e, 13) === true && ctx.goBack();
        }
      };

      if (el.__qgoback) {
        el.__qgoback_old = el.__qgoback;
      }

      el.__qgoback = ctx;
      el.addEventListener('click', ctx.goBack);
      el.addEventListener('keyup', ctx.goBackKey);
    },

    update: function update (el, ref) {
      var value = ref.value;
      var oldValue = ref.oldValue;
      var modifiers = ref.modifiers;

      var ctx = el.__qgoback;

      if (ctx !== void 0) {
        if (value !== oldValue) {
          ctx.value = value;
        }

        if (ctx.single !== modifiers.single) {
          ctx.single = modifiers.single;
        }
      }
    },

    unbind: function unbind (el) {
      var ctx = el.__qgoback_old || el.__qgoback;
      if (ctx !== void 0) {
        el.removeEventListener('click', ctx.goBack);
        el.removeEventListener('keyup', ctx.goBackKey);
        delete el[el.__qgoback_old ? '__qgoback_old' : '__qgoback'];
      }
    }
  };

  function objectWithoutProperties (obj, exclude) { var target = {}; for (var k in obj) if (Object.prototype.hasOwnProperty.call(obj, k) && exclude.indexOf(k) === -1) target[k] = obj[k]; return target; }

  var defaultCfg$1 = {
    childList: true,
    subtree: true,
    attributes: true,
    characterData: true,
    attributeOldValue: true,
    characterDataOldValue: true
  };

  function update$1 (el, ctx, ref) {
    var ref_modifiers = ref.modifiers;
    var once = ref_modifiers.once;
    var rest = objectWithoutProperties( ref_modifiers, ["once"] );
    var mod = rest;
    var value = ref.value;

    var changed;

    ctx.once = once;

    if (ctx.handler !== value) {
      changed = true;
      ctx.handler = value;
    }

    if (ctx.opts === void 0 || isDeepEqual(mod, ctx.mod) === false) {
      changed = true;
      ctx.mod = mod;
      ctx.opts = Object.keys(mod).length === 0
        ? defaultCfg$1
        : mod;
    }

    if (changed === true) {
      ctx.observer !== void 0 && ctx.observer.disconnect();

      ctx.observer = new MutationObserver(function (list) {
        if (typeof ctx.handler === 'function') {
          var res = ctx.handler(list);
          if (res === false || ctx.once === true) {
            destroy$1(el);
          }
        }
      });

      ctx.observer.observe(el, ctx.opts);
    }
  }

  function destroy$1 (el) {
    var ctx = el.__qmutation;

    if (ctx !== void 0) {
      ctx.observer !== void 0 && ctx.observer.disconnect();
      delete el.__qmutation;
    }
  }

  var Mutation = {
    name: 'mutation',

    inserted: function inserted (el, binding) {
      var ctx = {};
      update$1(el, ctx, binding);
      el.__qmutation = ctx;
    },

    update: function update$1$1 (el, binding) {
      var ctx = el.__qmutation;
      ctx !== void 0 && update$1(el, ctx, binding);
    },

    unbind: destroy$1
  };

  function updateBinding (ctx, ref) {
    var value = ref.value;
    var oldValue = ref.oldValue;

    if (typeof value !== 'function') {
      ctx.scrollTarget.removeEventListener('scroll', ctx.scroll);
      return
    }

    ctx.handler = value;
    if (typeof oldValue !== 'function') {
      ctx.scrollTarget.addEventListener('scroll', ctx.scroll, listenOpts.passive);
      ctx.scroll();
    }
  }

  var ScrollFire = {
    name: 'scroll-fire',

    bind: function bind (el) {
      var ctx = {
        scroll: debounce(function () {
          var containerBottom, elBottom;

          if (ctx.scrollTarget === window) {
            elBottom = el.getBoundingClientRect().bottom;
            containerBottom = window.innerHeight;
          }
          else {
            elBottom = offset(el).top + height(el);
            containerBottom = offset(ctx.scrollTarget).top + height(ctx.scrollTarget);
          }

          if (elBottom > 0 && elBottom < containerBottom) {
            ctx.scrollTarget.removeEventListener('scroll', ctx.scroll, listenOpts.passive);
            ctx.handler(el);
          }
        }, 25)
      };

      if (el.__qscrollfire) {
        el.__qscrollfire_old = el.__qscrollfire;
      }

      el.__qscrollfire = ctx;
    },

    inserted: function inserted (el, binding) {
      var ctx = el.__qscrollfire;
      ctx.scrollTarget = getScrollTarget(el);
      updateBinding(ctx, binding);
    },

    update: function update (el, binding) {
      if (el.__qscrollfire !== void 0 && binding.value !== binding.oldValue) {
        updateBinding(el.__qscrollfire, binding);
      }
    },

    unbind: function unbind (el) {
      var ctx = el.__qscrollfire_old || el.__qscrollfire;
      if (ctx !== void 0) {
        ctx.scrollTarget.removeEventListener('scroll', ctx.scroll, listenOpts.passive);
        delete el[el.__qscrollfire_old ? '__qscrollfire_old' : '__qscrollfire'];
      }
    }
  };

  function updateBinding$1 (ctx, ref) {
    var value = ref.value;
    var oldValue = ref.oldValue;

    if (typeof value !== 'function') {
      ctx.scrollTarget.removeEventListener('scroll', ctx.scroll, listenOpts.passive);
      return
    }

    ctx.handler = value;
    if (typeof oldValue !== 'function') {
      ctx.scrollTarget.addEventListener('scroll', ctx.scroll, listenOpts.passive);
    }
  }

  var Scroll = {
    name: 'scroll',

    bind: function bind (el) {
      var ctx = {
        scroll: function scroll () {
          ctx.handler(
            getScrollPosition(ctx.scrollTarget),
            getHorizontalScrollPosition(ctx.scrollTarget)
          );
        }
      };

      if (el.__qscroll) {
        el.__qscroll_old = el.__qscroll;
      }

      el.__qscroll = ctx;
    },

    inserted: function inserted (el, binding) {
      var ctx = el.__qscroll;
      ctx.scrollTarget = getScrollTarget(el);
      updateBinding$1(ctx, binding);
    },

    update: function update (el, binding) {
      if (el.__qscroll !== void 0 && binding.oldValue !== binding.value) {
        updateBinding$1(el.__qscroll, binding);
      }
    },

    unbind: function unbind (el) {
      var ctx = el.__qscroll_old || el.__qscroll;
      if (ctx !== void 0) {
        ctx.scrollTarget.removeEventListener('scroll', ctx.scroll, listenOpts.passive);
        delete el[el.__qscroll_old ? '__qscroll_old' : '__qscroll'];
      }
    }
  };

  function update$2 (el, binding) {
    var assign;

    var ctx = el.__qtouchhold;

    if (ctx !== void 0) {
      if (binding.oldValue !== binding.value) {
        typeof binding.value !== 'function' && ctx.end();
        ctx.handler = binding.value;
      }

      // duration in ms, touch in pixels, mouse in pixels
      var data = [600, 5, 7];

      if (typeof binding.arg === 'string' && binding.arg.length) {
        binding.arg.split(':').forEach(function (val, index) {
          var v = parseInt(val, 10);
          v && (data[index] = v);
        });
      }

      (assign = data, ctx.duration = assign[0], ctx.touchSensitivity = assign[1], ctx.mouseSensitivity = assign[2]);
    }
  }

  var TouchHold = {
    name: 'touch-hold',

    bind: function bind (el, binding) {
      var modifiers = binding.modifiers;

      // early return, we don't need to do anything
      if (modifiers.mouse !== true && client.has.touch !== true) {
        return
      }

      var ctx = {
        noop: noop,

        mouseStart: function mouseStart (evt) {
          if (typeof ctx.handler === 'function' && leftClick(evt) === true) {
            addEvt(ctx, 'temp', [
              [ document, 'mousemove', 'move', 'passiveCapture' ],
              [ document, 'click', 'end', 'notPassiveCapture' ]
            ]);
            ctx.start(evt, true);
          }
        },

        touchStart: function touchStart (evt) {
          if (evt.target !== void 0 && typeof ctx.handler === 'function') {
            var target = getTouchTarget(evt.target);
            addEvt(ctx, 'temp', [
              [ target, 'touchmove', 'move', 'passiveCapture' ],
              [ target, 'touchcancel', 'end', 'notPassiveCapture' ],
              [ target, 'touchend', 'end', 'notPassiveCapture' ]
            ]);
            ctx.start(evt);
          }
        },

        start: function start (evt, mouseEvent) {
          ctx.origin = position(evt);

          var startTime = Date.now();

          if (client.is.mobile === true) {
            document.body.classList.add('non-selectable');
            clearSelection();

            ctx.styleCleanup = function (withDelay) {
              ctx.styleCleanup = void 0;

              var remove = function () {
                document.body.classList.remove('non-selectable');
              };

              if (withDelay === true) {
                clearSelection();
                setTimeout(remove, 10);
              }
              else { remove(); }
            };
          }

          ctx.triggered = false;
          ctx.sensitivity = mouseEvent === true
            ? ctx.mouseSensitivity
            : ctx.touchSensitivity;

          ctx.timer = setTimeout(function () {
            clearSelection();
            ctx.triggered = true;

            ctx.handler({
              evt: evt,
              touch: mouseEvent !== true,
              mouse: mouseEvent === true,
              position: ctx.origin,
              duration: Date.now() - startTime
            });
          }, ctx.duration);
        },

        move: function move (evt) {
          var ref = position(evt);
          var top = ref.top;
          var left = ref.left;
          if (
            Math.abs(left - ctx.origin.left) >= ctx.sensitivity ||
            Math.abs(top - ctx.origin.top) >= ctx.sensitivity
          ) {
            clearTimeout(ctx.timer);
          }
        },

        end: function end (evt) {
          cleanEvt(ctx, 'temp');

          // delay needed otherwise selection still occurs
          ctx.styleCleanup !== void 0 && ctx.styleCleanup(ctx.triggered);

          if (ctx.triggered === true) {
            evt !== void 0 && stopAndPrevent(evt);
          }
          else {
            clearTimeout(ctx.timer);
          }
        }
      };

      if (el.__qtouchhold) {
        el.__qtouchhold_old = el.__qtouchhold;
      }

      el.__qtouchhold = ctx;

      update$2(el, binding);

      modifiers.mouse === true && addEvt(ctx, 'main', [
        [ el, 'mousedown', 'mouseStart', ("passive" + (modifiers.mouseCapture === true ? 'Capture' : '')) ]
      ]);

      client.has.touch === true && addEvt(ctx, 'main', [
        [ el, 'touchstart', 'touchStart', ("passive" + (modifiers.capture === true ? 'Capture' : '')) ],
        [ el, 'touchend', 'noop', 'notPassiveCapture' ]
      ]);
    },

    update: update$2,

    unbind: function unbind (el) {
      var ctx = el.__qtouchhold_old || el.__qtouchhold;
      if (ctx !== void 0) {
        cleanEvt(ctx, 'main');
        cleanEvt(ctx, 'temp');

        clearTimeout(ctx.timer);
        ctx.styleCleanup !== void 0 && ctx.styleCleanup();

        delete el[el.__qtouchhold_old ? '__qtouchhold_old' : '__qtouchhold'];
      }
    }
  };

  var
    keyCodes$2 = {
      esc: 27,
      tab: 9,
      enter: 13,
      space: 32,
      up: 38,
      left: 37,
      right: 39,
      down: 40,
      'delete': [8, 46]
    },
    keyRegex = new RegExp(("^([\\d+]+|" + (Object.keys(keyCodes$2).join('|')) + ")$"), 'i');

  function shouldEnd (evt, origin) {
    var ref = position(evt);
    var top = ref.top;
    var left = ref.left;

    return Math.abs(left - origin.left) >= 7 ||
      Math.abs(top - origin.top) >= 7
  }

  var TouchRepeat = {
    name: 'touch-repeat',

    bind: function bind (el, ref) {
      var modifiers = ref.modifiers;
      var value = ref.value;
      var arg = ref.arg;

      var keyboard = Object.keys(modifiers).reduce(function (acc, key) {
        if (keyRegex.test(key) === true) {
          var keyCode = isNaN(parseInt(key, 10)) ? keyCodes$2[key.toLowerCase()] : parseInt(key, 10);
          keyCode >= 0 && acc.push(keyCode);
        }
        return acc
      }, []);

      // early return, we don't need to do anything
      if (
        modifiers.mouse !== true &&
        client.has.touch !== true &&
        keyboard.length === 0
      ) {
        return
      }

      var durations = typeof arg === 'string' && arg.length > 0
        ? arg.split(':').map(function (val) { return parseInt(val, 10); })
        : [0, 600, 300];

      var durationsLast = durations.length - 1;

      var ctx = {
        keyboard: keyboard,
        handler: value,

        noop: noop,

        mouseStart: function mouseStart (evt) {
          if (ctx.event === void 0 && typeof ctx.handler === 'function' && leftClick(evt) === true) {
            addEvt(ctx, 'temp', [
              [ document, 'mousemove', 'move', 'passiveCapture' ],
              [ document, 'click', 'end', 'notPassiveCapture' ]
            ]);
            ctx.start(evt, true);
          }
        },

        keyboardStart: function keyboardStart (evt) {
          if (typeof ctx.handler === 'function' && isKeyCode(evt, keyboard) === true) {
            if (durations[0] === 0 || ctx.event !== void 0) {
              stopAndPrevent(evt);
              el.focus();
              if (ctx.event !== void 0) {
                return
              }
            }

            addEvt(ctx, 'temp', [
              [ document, 'keyup', 'end', 'notPassiveCapture' ],
              [ document, 'click', 'end', 'notPassiveCapture' ]
            ]);
            ctx.start(evt, false, true);
          }
        },

        touchStart: function touchStart (evt) {
          if (evt.target !== void 0 && typeof ctx.handler === 'function') {
            var target = getTouchTarget(evt.target);
            addEvt(ctx, 'temp', [
              [ target, 'touchmove', 'move', 'passiveCapture' ],
              [ target, 'touchcancel', 'end', 'notPassiveCapture' ],
              [ target, 'touchend', 'end', 'notPassiveCapture' ]
            ]);
            ctx.start(evt);
          }
        },

        start: function start (evt, mouseEvent, keyboardEvent) {
          if (keyboardEvent !== true) {
            ctx.origin = position(evt);
          }

          function styleCleanup (withDelay) {
            ctx.styleCleanup = void 0;

            document.documentElement.style.cursor = '';

            var remove = function () {
              document.body.classList.remove('non-selectable');
            };

            if (withDelay === true) {
              clearSelection();
              setTimeout(remove, 10);
            }
            else { remove(); }
          }

          if (client.is.mobile === true) {
            document.body.classList.add('non-selectable');
            clearSelection();
            ctx.styleCleanup = styleCleanup;
          }

          ctx.event = {
            touch: mouseEvent !== true && keyboardEvent !== true,
            mouse: mouseEvent === true,
            keyboard: keyboardEvent === true,
            startTime: Date.now(),
            repeatCount: 0
          };

          var fn = function () {
            if (ctx.event === void 0) {
              return
            }

            if (ctx.event.repeatCount === 0) {
              ctx.event.evt = evt;

              if (keyboardEvent === true) {
                ctx.event.keyCode = evt.keyCode;
              }
              else {
                ctx.event.position = position(evt);
              }

              if (client.is.mobile !== true) {
                document.documentElement.style.cursor = 'pointer';
                document.body.classList.add('non-selectable');
                clearSelection();
                ctx.styleCleanup = styleCleanup;
              }
            }

            ctx.event.duration = Date.now() - ctx.event.startTime;
            ctx.event.repeatCount += 1;

            ctx.handler(ctx.event);

            var index = durationsLast < ctx.event.repeatCount
              ? durationsLast
              : ctx.event.repeatCount;

            ctx.timer = setTimeout(fn, durations[index]);
          };

          if (durations[0] === 0) {
            fn();
          }
          else {
            ctx.timer = setTimeout(fn, durations[0]);
          }
        },

        move: function move (evt) {
          if (ctx.event !== void 0 && shouldEnd(evt, ctx.origin) === true) {
            clearTimeout(ctx.timer);
          }
        },

        end: function end (evt) {
          if (ctx.event === void 0) {
            return
          }

          ctx.styleCleanup !== void 0 && ctx.styleCleanup(true);
          evt !== void 0 && ctx.event.repeatCount > 0 && stopAndPrevent(evt);

          cleanEvt(ctx, 'temp');
          clearTimeout(ctx.timer);

          ctx.event = void 0;
        }
      };

      if (el.__qtouchrepeat !== void 0) {
        el.__qtouchrepeat_old = el.__qtouchrepeat;
      }

      el.__qtouchrepeat = ctx;

      modifiers.mouse === true && addEvt(ctx, 'main', [
        [ el, 'mousedown', 'mouseStart', ("passive" + (modifiers.mouseCapture === true ? 'Capture' : '')) ]
      ]);

      client.has.touch === true && addEvt(ctx, 'main', [
        [ el, 'touchstart', 'touchStart', ("passive" + (modifiers.capture === true ? 'Capture' : '')) ],
        [ el, 'touchend', 'noop', 'notPassiveCapture' ]
      ]);

      keyboard.length > 0 && addEvt(ctx, 'main', [
        [ el, 'keydown', 'keyboardStart', ("notPassive" + (modifiers.keyCapture === true ? 'Capture' : '')) ]
      ]);
    },

    update: function update (el, binding) {
      var ctx = el.__qtouchrepeat;

      if (ctx !== void 0 && binding.oldValue !== binding.value) {
        typeof binding.value !== 'function' && ctx.end();
        ctx.handler = binding.value;
      }
    },

    unbind: function unbind (el) {
      var ctx = el.__qtouchrepeat_old || el.__qtouchrepeat;

      if (ctx !== void 0) {
        clearTimeout(ctx.timer);

        cleanEvt(ctx, 'main');
        cleanEvt(ctx, 'temp');

        ctx.styleCleanup !== void 0 && ctx.styleCleanup();

        delete el[el.__qtouchrepeat_old ? '__qtouchrepeat_old' : '__qtouchrepeat'];
      }
    }
  };



  var directives = /*#__PURE__*/Object.freeze({
    __proto__: null,
    ClosePopup: ClosePopup,
    GoBack: GoBack,
    Intersection: Intersection,
    Mutation: Mutation,
    Ripple: Ripple,
    ScrollFire: ScrollFire,
    Scroll: Scroll,
    TouchHold: TouchHold,
    TouchPan: TouchPan,
    TouchRepeat: TouchRepeat,
    TouchSwipe: TouchSwipe
  });

  var metaValue;

  function getProp () {
    if (Platform.is.winphone) {
      return 'msapplication-navbutton-color'
    }
    if (Platform.is.safari) {
      return 'apple-mobile-web-app-status-bar-style'
    }
    // Chrome, Firefox OS, Opera, Vivaldi
    return 'theme-color'
  }

  function getMetaTag (v) {
    var els = document.getElementsByTagName('META');
    for (var i in els) {
      if (els[i].name === v) {
        return els[i]
      }
    }
  }

  function setColor (hexColor) {
    if (metaValue === void 0) {
      // cache it
      metaValue = getProp();
    }

    var metaTag = getMetaTag(metaValue);
    var newTag = metaTag === void 0;

    if (newTag) {
      metaTag = document.createElement('meta');
      metaTag.setAttribute('name', metaValue);
    }

    metaTag.setAttribute('content', hexColor);

    if (newTag) {
      document.head.appendChild(metaTag);
    }
  }

  var AddressbarColor = {
    install: function install (ref) {
      var $q = ref.$q;
      var cfg = ref.cfg;

      this.set = isSSR === false && Platform.is.mobile === true && (
        Platform.is.nativeMobile === true ||
        Platform.is.winphone === true || Platform.is.safari === true ||
        Platform.is.webkit === true || Platform.is.vivaldi === true
      )
        ? function (hexColor) {
          var val = hexColor || getBrand('primary');

          if (Platform.is.nativeMobile === true && window.StatusBar) {
            window.StatusBar.backgroundColorByHexString(val);
          }
          else {
            setColor(val);
          }
        }
        : noop;

      $q.addressbarColor = this;

      cfg.addressbarColor && this.set(cfg.addressbarColor);
    }
  };

  var prefixes = {};

  // needed for consistency across browsers,
  // including IE11 which does not return anything
  function promisify (target, fn) {
    try {
      var res = target[fn]();
      return res === void 0
        ? Promise.resolve()
        : res
    }
    catch (err) {
      return Promise.reject(err)
    }
  }

  var AppFullscreen = {
    isCapable: false,
    isActive: false,

    request: function request (target) {
      return this.isCapable && !this.isActive
        ? promisify(target || document.documentElement, prefixes.request)
        : this.__getErr()
    },

    exit: function exit () {
      return this.isCapable && this.isActive
        ? promisify(document, prefixes.exit)
        : this.__getErr()
    },

    toggle: function toggle (target) {
      return this.isActive
        ? this.exit()
        : this.request(target)
    },

    install: function install (ref) {
      var this$1 = this;
      var $q = ref.$q;

      $q.fullscreen = this;

      if (isSSR === true) { return }

      prefixes.request = [
        'requestFullscreen',
        'msRequestFullscreen', 'mozRequestFullScreen', 'webkitRequestFullscreen'
      ].find(function (request) { return document.documentElement[request]; });

      this.isCapable = prefixes.request !== void 0;

      if (this.isCapable === false) {
        // it means the browser does NOT support it
        this.__getErr = function () { return Promise.reject('Not capable'); };
        return
      }

      this.__getErr = function () { return Promise.resolve(); };

      prefixes.exit = [
        'exitFullscreen',
        'msExitFullscreen', 'mozCancelFullScreen', 'webkitExitFullscreen'
      ].find(function (exit) { return document[exit]; });

      this.isActive = !!(document.fullscreenElement ||
        document.mozFullScreenElement ||
        document.webkitFullscreenElement ||
        document.msFullscreenElement)

      ;[
        'onfullscreenchange',
        'onmsfullscreenchange', 'onwebkitfullscreenchange'
      ].forEach(function (evt) {
        document[evt] = function () {
          this$1.isActive = !this$1.isActive;
        };
      });

      Vue.util.defineReactive(this, 'isActive', this.isActive);
    }
  };

  var AppVisibility = {
    appVisible: false,

    install: function install (ref) {
      var this$1 = this;
      var $q = ref.$q;

      if (isSSR === true) {
        this.appVisible = $q.appVisible = true;
        return
      }

      var prop, evt;

      if (typeof document.hidden !== 'undefined') { // Opera 12.10 and Firefox 18 and later support
        prop = 'hidden';
        evt = 'visibilitychange';
      }
      else if (typeof document.msHidden !== 'undefined') {
        prop = 'msHidden';
        evt = 'msvisibilitychange';
      }
      else if (typeof document.webkitHidden !== 'undefined') {
        prop = 'webkitHidden';
        evt = 'webkitvisibilitychange';
      }

      var update = function () {
        this$1.appVisible = $q.appVisible = !document[prop];
      };

      update();

      if (evt && typeof document[prop] !== 'undefined') {
        Vue.util.defineReactive($q, 'appVisible', this.appVisible);
        document.addEventListener(evt, update, false);
      }
    }
  };

  var BottomSheet = Vue.extend({
    name: 'BottomSheetPlugin',

    mixins: [ DarkMixin ],

    inheritAttrs: false,

    props: {
      title: String,
      message: String,
      actions: Array,

      grid: Boolean,

      cardClass: [String, Array, Object],
      cardStyle: [String, Array, Object]
    },

    methods: {
      show: function show () {
        this.$refs.dialog.show();
      },

      hide: function hide () {
        this.$refs.dialog.hide();
      },

      onOk: function onOk (action) {
        this.$emit('ok', action);
        this.hide();
      },

      __getGrid: function __getGrid (h) {
        var this$1 = this;

        return this.actions.map(function (action) {
          var img = action.avatar || action.img;

          return action.label === void 0
            ? h(QSeparator, {
              staticClass: 'col-all',
              props: { dark: this$1.isDark }
            })
            : h('div', {
              staticClass: 'q-bottom-sheet__item q-hoverable q-focusable cursor-pointer relative-position',
              class: action.classes,
              attrs: { tabindex: 0 },
              on: {
                click: function () { return this$1.onOk(action); },
                keyup: function (e) {
                  e.keyCode === 13 && this$1.onOk(action);
                }
              }
            }, [
              h('div', { staticClass: 'q-focus-helper' }),

              action.icon
                ? h(QIcon, { props: { name: action.icon, color: action.color } })
                : (
                  img
                    ? h('img', {
                      attrs: { src: img },
                      staticClass: action.avatar ? 'q-bottom-sheet__avatar' : null
                    })
                    : h('div', { staticClass: 'q-bottom-sheet__empty-icon' })
                ),

              h('div', [ action.label ])
            ])
        })
      },

      __getList: function __getList (h) {
        var this$1 = this;

        return this.actions.map(function (action) {
          var img = action.avatar || action.img;

          return action.label === void 0
            ? h(QSeparator, { props: { spaced: true, dark: this$1.isDark } })
            : h(QItem, {
              staticClass: 'q-bottom-sheet__item',
              class: action.classes,
              props: {
                tabindex: 0,
                clickable: true,
                dark: this$1.isDark
              },
              on: {
                click: function () { return this$1.onOk(action); },
                keyup: function (e) {
                  e.keyCode === 13 && this$1.onOk(action);
                }
              }
            }, [
              h(QItemSection, { props: { avatar: true } }, [
                action.icon
                  ? h(QIcon, { props: { name: action.icon, color: action.color } })
                  : (
                    img
                      ? h('img', {
                        attrs: { src: img },
                        staticClass: action.avatar ? 'q-bottom-sheet__avatar' : null
                      })
                      : null
                  )
              ]),
              h(QItemSection, [ action.label ])
            ])
        })
      }
    },

    render: function render (h) {
      var this$1 = this;

      var child = [];

      if (this.title) {
        child.push(
          h(QCardSection, {
            staticClass: 'q-dialog__title'
          }, [ this.title ])
        );
      }

      if (this.message) {
        child.push(
          h(QCardSection, {
            staticClass: 'q-dialog__message scroll'
          }, [ this.message ])
        );
      }

      child.push(
        this.grid === true
          ? h('div', {
            staticClass: 'scroll row items-stretch justify-start'
          }, this.__getGrid(h))
          : h('div', { staticClass: 'scroll' }, this.__getList(h))
      );

      return h(QDialog, {
        ref: 'dialog',

        props: Object.assign({}, this.$attrs,
          {position: 'bottom'}),

        on: cache(this, 'hide', {
          hide: function () {
            this$1.$emit('hide');
          }
        })
      }, [
        h(QCard, {
          staticClass: "q-bottom-sheet q-bottom-sheet--" + (this.grid === true ? 'grid' : 'list') +
            (this.isDark === true ? ' q-bottom-sheet--dark q-dark' : ''),
          style: this.cardStyle,
          class: this.cardClass
        }, child)
      ])
    }
  });

  function objectWithoutProperties$1 (obj, exclude) { var target = {}; for (var k in obj) if (Object.prototype.hasOwnProperty.call(obj, k) && exclude.indexOf(k) === -1) target[k] = obj[k]; return target; }

  var ssrAPI = {
    onOk: function () { return ssrAPI; },
    okCancel: function () { return ssrAPI; },
    hide: function () { return ssrAPI; }
  };

  function globalDialog (DefaultComponent) {
    return function (ref) {
      var className = ref.className;
      var klass = ref.class;
      var style = ref.style;
      var component = ref.component;
      var root = ref.root;
      var parent = ref.parent;
      var rest = objectWithoutProperties$1( ref, ["className", "class", "style", "component", "root", "parent"] );
      var props = rest;

      if (isSSR === true) { return ssrAPI }

      klass !== void 0 && (props.cardClass = klass);
      style !== void 0 && (props.cardStyle = style);

      var
        okFns = [],
        cancelFns = [],
        API = {
          onOk: function onOk (fn) {
            okFns.push(fn);
            return API
          },
          onCancel: function onCancel (fn) {
            cancelFns.push(fn);
            return API
          },
          onDismiss: function onDismiss (fn) {
            okFns.push(fn);
            cancelFns.push(fn);
            return API
          },
          hide: function hide () {
            vm.$refs.dialog.hide();
            return API
          }
        };

      var node = document.createElement('div');
      document.body.appendChild(node);

      var emittedOK = false;

      var on = {
        ok: function (data) {
          emittedOK = true;
          okFns.forEach(function (fn) { fn(data); });
        },

        hide: function () {
          vm.$destroy();
          vm.$el.remove();
          vm = null;

          if (emittedOK !== true) {
            cancelFns.forEach(function (fn) { fn(); });
          }
        }
      };

      Vue.observable(props);

      var DialogComponent = component !== void 0
        ? component
        : DefaultComponent;

      var attrs = component === void 0
        ? props
        : void 0;

      var vm = new Vue({
        name: 'QGlobalDialog',

        el: node,
        parent: parent === void 0 ? root : parent,

        render: function render (h) {
          return h(DialogComponent, {
            ref: 'dialog',
            props: props,
            attrs: attrs,
            on: on
          })
        },

        mounted: function mounted () {
          this.$refs.dialog.show();
        }
      });

      return API
    }
  }

  var BottomSheet$1 = {
    install: function install (ref) {
      var $q = ref.$q;

      this.create = $q.bottomSheet = globalDialog(BottomSheet);
    }
  };

  function encode (string) {
    return encodeURIComponent(string)
  }

  function decode (string) {
    return decodeURIComponent(string)
  }

  function stringifyCookieValue (value) {
    return encode(value === Object(value) ? JSON.stringify(value) : '' + value)
  }

  function read (string) {
    if (string === '') {
      return string
    }

    if (string.indexOf('"') === 0) {
      // This is a quoted cookie as according to RFC2068, unescape...
      string = string.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, '\\');
    }

    // Replace server-side written pluses with spaces.
    // If we can't decode the cookie, ignore it, it's unusable.
    // If we can't parse the cookie, ignore it, it's unusable.
    string = decode(string.replace(/\+/g, ' '));

    try {
      string = JSON.parse(string);
    }
    catch (e) {}

    return string
  }

  function getString (msOffset) {
    var time = new Date();
    time.setMilliseconds(time.getMilliseconds() + msOffset);
    return time.toUTCString()
  }

  function parseExpireString (str) {
    var timestamp = 0;

    var days = str.match(/(\d+)d/);
    var hours = str.match(/(\d+)h/);
    var minutes = str.match(/(\d+)m/);
    var seconds = str.match(/(\d+)s/);

    if (days) { timestamp += days[1] * 864e+5; }
    if (hours) { timestamp += hours[1] * 36e+5; }
    if (minutes) { timestamp += minutes[1] * 6e+4; }
    if (seconds) { timestamp += seconds[1] * 1000; }

    return timestamp === 0
      ? str
      : getString(timestamp)
  }

  function set (key, val, opts, ssr) {
    if ( opts === void 0 ) opts = {};

    var expire, expireValue;

    if (opts.expires !== void 0) {
      // if it's a Date Object
      if (Object.prototype.toString.call(opts.expires) === '[object Date]') {
        expire = opts.expires.toUTCString();
      }
      // if it's a String (eg. "15m", "1h", "13d", "1d 15m", "31s")
      // possible units: d (days), h (hours), m (minutes), s (seconds)
      else if (typeof opts.expires === 'string') {
        expire = parseExpireString(opts.expires);
      }
      // otherwise it must be a Number (defined in days)
      else {
        expireValue = parseFloat(opts.expires);
        expire = isNaN(expireValue) === false
          ? getString(expireValue * 864e+5)
          : opts.expires;
      }
    }

    var keyValue = (encode(key)) + "=" + (stringifyCookieValue(val));

    var cookie = [
      keyValue,
      expire !== void 0 ? '; Expires=' + expire : '', // use expires attribute, max-age is not supported by IE
      opts.path ? '; Path=' + opts.path : '',
      opts.domain ? '; Domain=' + opts.domain : '',
      opts.sameSite ? '; SameSite=' + opts.sameSite : '',
      opts.httpOnly ? '; HttpOnly' : '',
      opts.secure ? '; Secure' : '',
      opts.other ? '; ' + opts.other : ''
    ].join('');

    if (ssr) {
      if (ssr.req.qCookies) {
        ssr.req.qCookies.push(cookie);
      }
      else {
        ssr.req.qCookies = [ cookie ];
      }

      ssr.res.setHeader('Set-Cookie', ssr.req.qCookies);

      // make temporary update so future get()
      // within same SSR timeframe would return the set value

      var all = ssr.req.headers.cookie || '';

      if (expire !== void 0 && expireValue < 0) {
        var val$1 = get(key, ssr);
        if (val$1 !== undefined) {
          all = all
            .replace((key + "=" + val$1 + "; "), '')
            .replace(("; " + key + "=" + val$1), '')
            .replace((key + "=" + val$1), '');
        }
      }
      else {
        all = all
          ? (keyValue + "; " + all)
          : cookie;
      }

      ssr.req.headers.cookie = all;
    }
    else {
      document.cookie = cookie;
    }
  }

  function get (key, ssr) {
    var
      result = key ? null : {},
      cookieSource = ssr ? ssr.req.headers : document,
      cookies = cookieSource.cookie ? cookieSource.cookie.split('; ') : [],
      i = 0,
      l = cookies.length,
      parts,
      name,
      cookie;

    for (; i < l; i++) {
      parts = cookies[i].split('=');
      name = decode(parts.shift());
      cookie = parts.join('=');

      if (!key) {
        result[name] = cookie;
      }
      else if (key === name) {
        result = read(cookie);
        break
      }
    }

    return result
  }

  function remove (key, options, ssr) {
    set(
      key,
      '',
      Object.assign({}, {expires: -1}, options),
      ssr
    );
  }

  function has (key, ssr) {
    return get(key, ssr) !== null
  }

  function getObject (ctx) {
    if ( ctx === void 0 ) ctx = {};

    var ssr = ctx.ssr;

    return {
      get: function (key) { return get(key, ssr); },
      set: function (key, val, opts) { return set(key, val, opts, ssr); },
      has: function (key) { return has(key, ssr); },
      remove: function (key, options) { return remove(key, options, ssr); },
      getAll: function () { return get(null, ssr); }
    }
  }

  var Cookies = {
    parseSSR: function parseSSR (/* ssrContext */ ssr) {
      return ssr ? getObject({ ssr: ssr }) : this
    },

    install: function install (ref) {
      var $q = ref.$q;
      var queues = ref.queues;

      if (isSSR === true) {
        queues.server.push(function (q, ctx) {
          q.cookies = getObject(ctx);
        });
      }
      else {
        Object.assign(this, getObject());
        $q.cookies = this;
      }
    }
  };

  var DialogPlugin = Vue.extend({
    name: 'DialogPlugin',

    mixins: [ DarkMixin ],

    inheritAttrs: false,

    props: {
      title: String,
      message: String,
      prompt: Object,
      options: Object,

      html: Boolean,

      ok: {
        type: [String, Object, Boolean],
        default: true
      },
      cancel: [String, Object, Boolean],
      focus: {
        type: String,
        default: 'ok',
        validator: function (v) { return ['ok', 'cancel', 'none'].includes(v); }
      },

      stackButtons: Boolean,
      color: String,

      cardClass: [String, Array, Object],
      cardStyle: [String, Array, Object]
    },

    computed: {
      hasForm: function hasForm () {
        return this.prompt !== void 0 || this.options !== void 0
      },

      okLabel: function okLabel () {
        return Object(this.ok) === this.ok
          ? this.$q.lang.label.ok
          : (
            this.ok === true
              ? this.$q.lang.label.ok
              : this.ok
          )
      },

      cancelLabel: function cancelLabel () {
        return Object(this.cancel) === this.cancel
          ? this.$q.lang.label.cancel
          : (
            this.cancel === true
              ? this.$q.lang.label.cancel
              : this.cancel
          )
      },

      vmColor: function vmColor () {
        return this.color || (this.isDark === true ? 'amber' : 'primary')
      },

      okDisabled: function okDisabled () {
        if (this.prompt !== void 0) {
          return this.prompt.isValid !== void 0 &&
            this.prompt.isValid(this.prompt.model) !== true
        }
        if (this.options !== void 0) {
          return this.options.isValid !== void 0 &&
            this.options.isValid(this.options.model) !== true
        }
      },

      okProps: function okProps () {
        return Object.assign(
          {
            color: this.vmColor,
            label: this.okLabel,
            ripple: false
          },
          Object(this.ok) === this.ok
            ? this.ok
            : { flat: true },
          { disable: this.okDisabled }
        )
      },

      cancelProps: function cancelProps () {
        return Object.assign(
          {
            color: this.vmColor,
            label: this.cancelLabel,
            ripple: false
          },
          Object(this.cancel) === this.cancel
            ? this.cancel
            : { flat: true }
        )
      }
    },

    methods: {
      show: function show () {
        this.$refs.dialog.show();
      },

      hide: function hide () {
        this.$refs.dialog.hide();
      },

      getPrompt: function getPrompt (h) {
        var this$1 = this;

        return [
          h(QInput, {
            props: {
              value: this.prompt.model,
              type: this.prompt.type,
              label: this.prompt.label,
              stackLabel: this.prompt.stackLabel,
              outlined: this.prompt.outlined,
              filled: this.prompt.filled,
              standout: this.prompt.standout,
              color: this.vmColor,
              dense: true,
              autofocus: true,
              dark: this.isDark
            },
            on: cache(this, 'prompt', {
              input: function (v) { this$1.prompt.model = v; },
              keyup: function (evt) {
                // if ENTER key
                if (
                  this$1.okDisabled !== true &&
                  this$1.prompt.type !== 'textarea' &&
                  isKeyCode(evt, 13) === true
                ) {
                  this$1.onOk();
                }
              }
            })
          })
        ]
      },

      getOptions: function getOptions (h) {
        var this$1 = this;

        return [
          h(QOptionGroup, {
            props: {
              value: this.options.model,
              type: this.options.type,
              color: this.vmColor,
              inline: this.options.inline,
              options: this.options.items,
              dark: this.isDark
            },
            on: cache(this, 'opts', {
              input: function (v) { this$1.options.model = v; }
            })
          })
        ]
      },

      getButtons: function getButtons (h) {
        var child = [];

        this.cancel && child.push(h(QBtn, {
          props: this.cancelProps,
          attrs: { 'data-autofocus': this.focus === 'cancel' && this.hasForm !== true },
          on: cache(this, 'cancel', { click: this.onCancel })
        }));

        this.ok && child.push(h(QBtn, {
          props: this.okProps,
          attrs: { 'data-autofocus': this.focus === 'ok' && this.hasForm !== true },
          on: cache(this, 'ok', { click: this.onOk })
        }));

        if (child.length > 0) {
          return h(QCardActions, {
            staticClass: this.stackButtons === true ? 'items-end' : null,
            props: {
              vertical: this.stackButtons,
              align: 'right'
            }
          }, child)
        }
      },

      onOk: function onOk () {
        this.$emit('ok', clone$1(this.getData()));
        this.hide();
      },

      onCancel: function onCancel () {
        this.hide();
      },

      getData: function getData () {
        return this.prompt !== void 0
          ? this.prompt.model
          : (this.options !== void 0 ? this.options.model : void 0)
      },

      getSection: function getSection (h, staticClass, text) {
        return this.html === true
          ? h(QCardSection, {
            staticClass: staticClass,
            domProps: { innerHTML: text }
          })
          : h(QCardSection, { staticClass: staticClass }, [ text ])
      }
    },

    render: function render (h) {
      var this$1 = this;

      var child = [];

      this.title && child.push(
        this.getSection(h, 'q-dialog__title', this.title)
      );

      this.message && child.push(
        this.getSection(h, 'q-dialog__message scroll', this.message)
      );

      this.hasForm === true && child.push(
        h(
          QCardSection,
          { staticClass: 'scroll' },
          this.prompt !== void 0
            ? this.getPrompt(h)
            : this.getOptions(h)
        )
      );

      if (this.ok || this.cancel) {
        child.push(this.getButtons(h));
      }

      return h(QDialog, {
        ref: 'dialog',

        props: Object.assign({}, this.$attrs,
          {value: this.value}),

        on: cache(this, 'hide', {
          hide: function () {
            this$1.$emit('hide');
          }
        })
      }, [
        h(QCard, {
          staticClass: 'q-dialog-plugin' +
            (this.isDark === true ? ' q-dialog-plugin--dark q-dark' : ''),
          style: this.cardStyle,
          class: this.cardClass,
          props: { dark: this.isDark }
        }, child)
      ])
    }
  });

  var Dialog = {
    install: function install (ref) {
      var $q = ref.$q;

      this.create = $q.dialog = globalDialog(DialogPlugin);
    }
  };

  var LoadingBar = {
    isActive: false,
    start: noop,
    stop: noop,
    increment: noop,
    setDefaults: noop,

    install: function install (ref) {
      var this$1 = this;
      var $q = ref.$q;
      var cfg = ref.cfg;

      if (isSSR === true) {
        $q.loadingBar = this;
        return
      }

      var props = cfg.loadingBar !== void 0
        ? Object.assign({}, cfg.loadingBar)
        : {};

      var bar = $q.loadingBar = new Vue({
        name: 'LoadingBar',
        render: function (h) { return h(QAjaxBar, {
          ref: 'bar',
          props: props
        }); }
      }).$mount().$refs.bar;

      Object.assign(this, {
        start: function (speed) {
          bar.start(speed);
          this$1.isActive = bar.isActive = bar.calls > 0;
        },
        stop: function () {
          bar.stop();
          this$1.isActive = bar.isActive = bar.calls > 0;
        },
        increment: bar.increment,
        setDefaults: function (opts) {
          opts === Object(opts) && Object.assign(props, opts);
          bar.$parent.$forceUpdate();
        }
      });

      Vue.util.defineReactive(this, 'isActive', this.isActive);
      Vue.util.defineReactive(bar, 'isActive', this.isActive);
      bar.setDefaults = this.setDefaults;

      document.body.appendChild(bar.$parent.$el);
    }
  };

  var
    vm,
    uid$3 = 0,
    timeout,
    props = {},
    originalDefaults = {
      delay: 0,
      message: false,
      spinnerSize: 80,
      spinnerColor: 'white',
      messageColor: 'white',
      backgroundColor: 'black',
      spinner: QSpinner,
      customClass: ''
    },
    defaults = Object.assign({}, originalDefaults);

  var Loading = {
    isActive: false,

    show: function show (opts) {
      var this$1 = this;

      if (isSSR === true) { return }

      props = opts === Object(opts) && opts.ignoreDefaults === true
        ? Object.assign({}, originalDefaults, opts)
        : Object.assign({}, defaults, opts);

      props.customClass += " text-" + (props.backgroundColor);
      props.uid = "l_" + (uid$3++);

      this.isActive = true;

      if (vm !== void 0) {
        vm.$forceUpdate();
        return
      }

      clearTimeout(timeout);
      timeout = setTimeout(function () {
        timeout = void 0;

        var node = document.createElement('div');
        document.body.appendChild(node);

        vm = new Vue({
          name: 'QLoading',

          el: node,

          mounted: function mounted () {
            preventScroll(true, client);
          },

          render: function (h) {
            var obj;

            return h('transition', {
              props: {
                name: 'q-transition--fade',
                appear: true
              },
              on: cache(this$1, 'tr', {
                'after-leave': function () {
                  // might be called to finalize
                  // previous leave, even if it was cancelled
                  if (this$1.isActive !== true && vm !== void 0) {
                    preventScroll(false, client);
                    vm.$destroy();
                    vm.$el.remove();
                    vm = void 0;
                  }
                }
              })
            }, [
              this$1.isActive === true ? h('div', {
                staticClass: 'q-loading fullscreen column flex-center z-max',
                key: props.uid,
                class: props.customClass.trim()
              }, [
                h(props.spinner, {
                  props: {
                    color: props.spinnerColor,
                    size: props.spinnerSize
                  }
                }),
                (props.message && h('div', {
                  class: ("text-" + (props.messageColor)),
                  domProps: ( obj = {}, obj[props.sanitize === true ? 'textContent' : 'innerHTML'] = props.message, obj )
                })) || void 0
              ]) : null
            ])
          }
        });
      }, props.delay);
    },

    hide: function hide () {
      if (this.isActive === true) {
        if (timeout !== void 0) {
          clearTimeout(timeout);
          timeout = void 0;
        }

        this.isActive = false;
      }
    },

    setDefaults: function setDefaults (opts) {
      opts === Object(opts) && Object.assign(defaults, opts);
    },

    install: function install (ref) {
      var $q = ref.$q;
      var loading = ref.cfg.loading;

      this.setDefaults(loading);
      $q.loading = this;
    }
  };

  if (isSSR === false) {
    Vue.util.defineReactive(Loading, 'isActive', Loading.isActive);
  }

  var updateId, ssrTakeover;

  function normalize (meta) {
    if (meta.title) {
      meta.title = meta.titleTemplate
        ? meta.titleTemplate(meta.title)
        : meta.title;
      delete meta.titleTemplate;
    }
  [['meta', 'content'], ['link', 'href']].forEach(function (type) {
      var
        metaType = meta[type[0]],
        metaProp = type[1];

      for (var name in metaType) {
        var metaLink = metaType[name];

        if (metaLink.template) {
          if (Object.keys(metaLink).length === 1) {
            delete metaType[name];
          }
          else {
            metaLink[metaProp] = metaLink.template(metaLink[metaProp] || '');
            delete metaLink.template;
          }
        }
      }
    });
  }

  function changed (old, def) {
    if (Object.keys(old).length !== Object.keys(def).length) {
      return true
    }
    for (var key in old) {
      if (old[key] !== def[key]) {
        return true
      }
    }
  }

  function bodyFilter (name) {
    return ['class', 'style'].includes(name) === false
  }

  function htmlFilter (name) {
    return ['lang', 'dir'].includes(name) === false
  }

  function diff (meta, other) {
    var add = {}, remove = {};

    if (meta === void 0) {
      return { add: other, remove: remove }
    }

    if (meta.title !== other.title) {
      add.title = other.title;
    }
  ['meta', 'link', 'script', 'htmlAttr', 'bodyAttr'].forEach(function (type) {
      var old = meta[type], cur = other[type];
      remove[type] = [];

      if (old === void 0 || old === null) {
        add[type] = cur;
        return
      }

      add[type] = {};

      for (var key in old) {
        if (cur.hasOwnProperty(key) === false) {
          remove[type].push(key);
        }
      }
      for (var key$1 in cur) {
        if (old.hasOwnProperty(key$1) === false) {
          add[type][key$1] = cur[key$1];
        }
        else if (changed(old[key$1], cur[key$1]) === true) {
          remove[type].push(key$1);
          add[type][key$1] = cur[key$1];
        }
      }
    });

    return { add: add, remove: remove }
  }

  function apply$1 (ref) {
    var add = ref.add;
    var remove = ref.remove;

    if (add.title) {
      document.title = add.title;
    }

    if (Object.keys(remove).length > 0) {
      ['meta', 'link', 'script'].forEach(function (type) {
        remove[type].forEach(function (name) {
          document.head.querySelector((type + "[data-qmeta=\"" + name + "\"]")).remove();
        });
      });
      remove.htmlAttr.filter(htmlFilter).forEach(function (name) {
        document.documentElement.removeAttribute(name);
      });
      remove.bodyAttr.filter(bodyFilter).forEach(function (name) {
        document.body.removeAttribute(name);
      });
    }
  ['meta', 'link', 'script'].forEach(function (type) {
      var metaType = add[type];

      for (var name in metaType) {
        var tag = document.createElement(type);
        for (var att in metaType[name]) {
          if (att !== 'innerHTML') {
            tag.setAttribute(att, metaType[name][att]);
          }
        }
        tag.setAttribute('data-qmeta', name);
        if (type === 'script') {
          tag.innerHTML = metaType[name].innerHTML || '';
        }
        document.head.appendChild(tag);
      }
    });
    Object.keys(add.htmlAttr).filter(htmlFilter).forEach(function (name) {
      document.documentElement.setAttribute(name, add.htmlAttr[name] || '');
    });
    Object.keys(add.bodyAttr).filter(bodyFilter).forEach(function (name) {
      document.body.setAttribute(name, add.bodyAttr[name] || '');
    });
  }

  function parseMeta (component, meta) {
    if (component._inactive === true) { return }

    // if it has meta
    if (hasMeta(component) === true) {
      extend(true, meta, component.__qMeta);

      if (component.$options.meta.stopPropagation === true) {
        return
      }
    }

    component.$children.forEach(function (child) {
      parseMeta(child, meta);
    });
  }

  function updateClient () {
    if (ssrTakeover === true) {
      ssrTakeover = false;
      this.$root.__currentMeta = window.__Q_META__;
      document.body.querySelector('script[data-qmeta-init]').remove();
      return
    }

    var meta = {
      title: '',
      titleTemplate: null,
      meta: {},
      link: {},
      script: {},
      htmlAttr: {},
      bodyAttr: {}
    };
    parseMeta(this.$root, meta);
    normalize(meta);

    apply$1(diff(this.$root.__currentMeta, meta));
    this.$root.__currentMeta = meta;
  }

  function getAttr (seed) {
    return function (att) {
      var val = seed[att];
      return att + (val !== void 0 ? ("=\"" + val + "\"") : '')
    }
  }

  function getHead (meta) {
    var output = '';
    if (meta.title) {
      output += "<title>" + (meta.title) + "</title>";
    }
  ['meta', 'link', 'script'].forEach(function (type) {
      var metaType = meta[type];

      for (var att in metaType) {
        var attrs = Object.keys(metaType[att])
          .filter(function (att) { return att !== 'innerHTML'; })
          .map(getAttr(metaType[att]));

        output += "<" + type + " " + (attrs.join(' ')) + " data-qmeta=\"" + att + "\">";
        if (type === 'script') {
          output += (metaType[att].innerHTML || '') + "</script>";
        }
      }
    });
    return output
  }

  function getServerMeta (app, html) {
    var meta = {
      title: '',
      titleTemplate: null,
      meta: {},
      link: {},
      htmlAttr: {},
      bodyAttr: {},
      noscript: {}
    };

    parseMeta(app, meta);
    normalize(meta);

    var tokens = {
      '%%Q_HTML_ATTRS%%': Object.keys(meta.htmlAttr)
        .filter(htmlFilter)
        .map(getAttr(meta.htmlAttr))
        .join(' '),
      '%%Q_HEAD_TAGS%%': getHead(meta),
      '%%Q_BODY_ATTRS%%': Object.keys(meta.bodyAttr)
        .filter(bodyFilter)
        .map(getAttr(meta.bodyAttr))
        .join(' '),
      '%%Q_BODY_TAGS%%': Object.keys(meta.noscript)
        .map(function (name) { return ("<noscript data-qmeta=\"" + name + "\">" + (meta.noscript[name]) + "</noscript>"); })
        .join('') +
        "<script data-qmeta-init>window.__Q_META__=" + (delete meta.noscript && JSON.stringify(meta)) + "</script>"
    };

    Object.keys(tokens).forEach(function (key) {
      html = html.replace(key, tokens[key]);
    });

    return html
  }

  function beforeCreate () {
    if (typeof this.$options.meta === 'function') {
      if (this.$options.computed === void 0) {
        this.$options.computed = {};
      }
      this.$options.computed.__qMeta = this.$options.meta;
    }
    else if (hasMeta(this) === true) {
      this.__qMeta = this.$options.meta;
    }
  }

  // needs to be really fast
  function hasMeta (vm) {
    return vm.$options.meta !== void 0 &&
      vm.$options.meta !== null
  }

  function triggerMeta () {
    hasMeta(this) === true && this.__qMetaUpdate();
  }

  var Meta = {
    install: function install (ref) {
      var queues = ref.queues;

      if (isSSR === true) {
        Vue.prototype.$getMetaHTML = function (app) { return function (html) { return getServerMeta(app, html); }; };
        Vue.mixin({ beforeCreate: beforeCreate });

        queues.server.push(function (_, ctx) {
          ctx.ssr.Q_HTML_ATTRS += ' %%Q_HTML_ATTRS%%';
          Object.assign(ctx.ssr, {
            Q_HEAD_TAGS: '%%Q_HEAD_TAGS%%',
            Q_BODY_ATTRS: '%%Q_BODY_ATTRS%%',
            Q_BODY_TAGS: '%%Q_BODY_TAGS%%'
          });
        });
      }
      else {
        ssrTakeover = fromSSR;

        Vue.mixin({
          beforeCreate: beforeCreate,
          created: function created () {
            if (hasMeta(this) === true) {
              this.__qMetaUnwatch = this.$watch('__qMeta', this.__qMetaUpdate);
            }
          },
          activated: triggerMeta,
          deactivated: triggerMeta,
          beforeMount: triggerMeta,
          destroyed: function destroyed () {
            if (hasMeta(this) === true) {
              this.__qMetaUnwatch();
              this.__qMetaUpdate();
            }
          },
          methods: {
            __qMetaUpdate: function __qMetaUpdate () {
              clearTimeout(updateId);
              updateId = setTimeout(updateClient.bind(this), 50);
            }
          }
        });
      }
    }
  };

  function objectWithoutProperties$2 (obj, exclude) { var target = {}; for (var k in obj) if (Object.prototype.hasOwnProperty.call(obj, k) && exclude.indexOf(k) === -1) target[k] = obj[k]; return target; }

  var uid$4 = 0;
  var defaults$1 = {};

  var attrs$2 = { role: 'alert' };

  var positionList = [
    'top-left', 'top-right',
    'bottom-left', 'bottom-right',
    'top', 'bottom', 'left', 'right', 'center'
  ];

  var badgePositions = [
    'top-left', 'top-right',
    'bottom-left', 'bottom-right'
  ];

  var notifTypes = {
    positive: {
      icon: function icon () { return this.$q.iconSet.type.positive },
      color: 'positive'
    },

    negative: {
      icon: function icon () { return this.$q.iconSet.type.negative },
      color: 'negative'
    },

    warning: {
      icon: function icon () { return this.$q.iconSet.type.warning },
      color: 'warning',
      textColor: 'dark'
    },

    info: {
      icon: function icon () { return this.$q.iconSet.type.info },
      color: 'info'
    }
  };

  var groups = {};
  var positionClass$1 = {};

  var Notifications = {
    name: 'QNotifications',

    created: function created () {
      var this$1 = this;

      this.notifs = {};

      positionList.forEach(function (pos) {
        this$1.notifs[pos] = [];

        var
          vert = ['left', 'center', 'right'].includes(pos) ? 'center' : (pos.indexOf('top') > -1 ? 'top' : 'bottom'),
          align = pos.indexOf('left') > -1 ? 'start' : (pos.indexOf('right') > -1 ? 'end' : 'center'),
          classes = ['left', 'right'].includes(pos) ? ("items-" + (pos === 'left' ? 'start' : 'end') + " justify-center") : (pos === 'center' ? 'flex-center' : ("items-" + align));

        positionClass$1[pos] = "q-notifications__list q-notifications__list--" + vert + " fixed column no-wrap " + classes;
      });
    },

    methods: {
      add: function add (config) {
        var this$1 = this;

        if (!config) {
          console.error('Notify: parameter required');
          return false
        }

        var notif = { textColor: 'white' };

        if (typeof config === 'string' || config.ignoreDefaults !== true) {
          Object.assign(notif, defaults$1);
        }

        if (Object(config) === config) {
          Object.assign(notif, notifTypes[config.type], config);

          if (typeof notif.icon === 'function') {
            notif.icon = notif.icon.call(this);
          }
        }
        else {
          Object.assign(notif, { message: config });
        }

        notif.meta = {
          hasMedia: Boolean(notif.icon || notif.avatar)
        };

        if (notif.position) {
          if (!positionList.includes(notif.position)) {
            console.error(("Notify: wrong position: " + (notif.position)));
            return false
          }
        }
        else {
          notif.position = 'bottom';
        }

        if (notif.timeout === void 0) {
          notif.timeout = 5000;
        }
        else {
          var t = parseInt(notif.timeout, 10);
          if (isNaN(t) || t < 0) {
            console.error(("Notify: wrong timeout: " + (notif.timeout)));
            return false
          }
          notif.timeout = t;
        }

        if (notif.timeout === 0) {
          notif.progress = false;
        }
        else if (notif.progress === true) {
          notif.meta.progressStyle = {
            animationDuration: ((notif.timeout + 1000) + "ms")
          };
        }

        var actions = (Array.isArray(config.actions) === true ? config.actions : [])
          .concat(config.ignoreDefaults !== true && Array.isArray(defaults$1.actions) === true ? defaults$1.actions : []);

        notif.closeBtn && actions.push({
          label: typeof notif.closeBtn === 'string'
            ? notif.closeBtn
            : this.$q.lang.label.close
        });

        notif.actions = actions.map(function (ref) {
          var handler = ref.handler;
          var noDismiss = ref.noDismiss;
          var rest = objectWithoutProperties$2( ref, ["handler", "noDismiss"] );
          var item = rest;

          return ({
          props: Object.assign({}, {flat: true}, item),
          on: {
            click: typeof handler === 'function'
              ? function () {
                handler();
                noDismiss !== true && notif.meta.close();
              }
              : function () {
                notif.meta.close();
              }
          }
        });
        });

        if (notif.multiLine === void 0) {
          notif.multiLine = notif.actions.length > 1;
        }

        Object.assign(notif.meta, {
          staticClass: "q-notification row items-stretch" +
            " q-notification--" + (notif.multiLine === true ? 'multi-line' : 'standard') +
            (notif.color !== void 0 ? (" bg-" + (notif.color)) : '') +
            (notif.textColor !== void 0 ? (" text-" + (notif.textColor)) : '') +
            (notif.classes !== void 0 ? (" " + (notif.classes)) : ''),

          wrapperClass: 'q-notification__wrapper col relative-position border-radius-inherit ' +
            (notif.multiLine === true ? 'column no-wrap justify-center' : 'row items-center'),

          contentClass: 'q-notification__content row items-center' +
            (notif.multiLine === true ? '' : ' col')
        });

        if (notif.group === false) {
          notif.group = void 0;
        }
        else {
          if (notif.group === void 0 || notif.group === true) {
            // do not replace notifications with different buttons
            notif.group = [
              notif.message,
              notif.caption,
              notif.multiline
            ].concat(
              notif.actions.map(function (a) { return ((a.props.label) + "*" + (a.props.icon)); })
            ).join('|');
          }

          notif.group += '|' + notif.position;
        }

        if (notif.actions.length === 0) {
          notif.actions = void 0;
        }
        else {
          notif.meta.actionsClass = 'q-notification__actions row items-center ' +
            (notif.multiLine === true ? 'justify-end' : 'col-auto') +
            (notif.meta.hasMedia === true ? ' q-notification__actions--with-media' : '');
        }

        var groupNotif = groups[notif.group];

        // wohoo, new notification
        if (groupNotif === void 0) {
          notif.meta.uid = uid$4++;
          notif.meta.badge = 1;

          if (['left', 'right', 'center'].indexOf(notif.position) !== -1) {
            this.notifs[notif.position].splice(
              Math.floor(this.notifs[notif.position].length / 2),
              0,
              notif
            );
          }
          else {
            var action = notif.position.indexOf('top') > -1 ? 'unshift' : 'push';
            this.notifs[notif.position][action](notif);
          }

          if (notif.group !== void 0) {
            groups[notif.group] = notif;
          }
        }
        // ok, so it's NOT a new one
        else {
          // reset timeout if any
          if (groupNotif.meta.timer !== void 0) {
            clearTimeout(groupNotif.meta.timer);
          }

          var original = groups[notif.group];

          if (notif.badgePosition !== void 0) {
            if (badgePositions.includes(notif.badgePosition) === false) {
              console.error(("Notify - wrong badgePosition specified: " + (notif.badgePosition)));
              return false
            }
          }
          else {
            notif.badgePosition = "top-" + (notif.position.indexOf('left') > -1 ? 'right' : 'left');
          }

          notif.meta.uid = original.meta.uid;
          notif.meta.badge = original.meta.badge + 1;
          notif.meta.badgeStaticClass = "q-notification__badge q-notification__badge--" + (notif.badgePosition) +
            (notif.badgeColor !== void 0 ? (" bg-" + (notif.badgeColor)) : '') +
            (notif.badgeTextColor !== void 0 ? (" text-" + (notif.badgeTextColor)) : '');

          notif = Object.assign(original, notif);
        }

        notif.meta.close = function () {
          this$1.remove(notif);
        };

        this.$forceUpdate();

        if (notif.timeout > 0) {
          notif.meta.timer = setTimeout(function () {
            notif.meta.close();
          }, notif.timeout + /* show duration */ 1000);
        }

        return notif.meta.close
      },

      remove: function remove (notif) {
        if (notif.meta.timer) { clearTimeout(notif.meta.timer); }

        var index = this.notifs[notif.position].indexOf(notif);
        if (index !== -1) {
          if (notif.group !== void 0) {
            delete groups[notif.group];
          }

          var el = this.$refs[("notif_" + (notif.meta.uid))];

          if (el) {
            var ref = getComputedStyle(el);
            var width = ref.width;
            var height = ref.height;

            el.style.left = (el.offsetLeft) + "px";
            el.style.width = width;
            el.style.height = height;
          }

          this.notifs[notif.position].splice(index, 1);

          this.$forceUpdate();

          if (typeof notif.onDismiss === 'function') {
            notif.onDismiss();
          }
        }
      }
    },

    render: function render (h) {
      var this$1 = this;

      return h('div', { staticClass: 'q-notifications' }, positionList.map(function (pos) {
        return h('transition-group', {
          key: pos,
          staticClass: positionClass$1[pos],
          tag: 'div',
          props: {
            name: ("q-notification--" + pos),
            mode: 'out-in'
          }
        }, this$1.notifs[pos].map(function (notif) {
          var msgChild;

          var meta = notif.meta;
          var msgData = { staticClass: 'q-notification__message col' };

          if (notif.html === true) {
            msgData.domProps = {
              innerHTML: notif.caption
                ? ("<div>" + (notif.message) + "</div><div class=\"q-notification__caption\">" + (notif.caption) + "</div>")
                : notif.message
            };
          }
          else {
            var msgNode = [ notif.message ];
            msgChild = notif.caption
              ? [
                h('div', msgNode),
                h('div', { staticClass: 'q-notification__caption' }, [ notif.caption ])
              ]
              : msgNode;
          }

          var mainChild = [];

          if (meta.hasMedia === true) {
            if (notif.icon) {
              mainChild.push(
                h(QIcon, {
                  staticClass: 'q-notification__icon col-auto',
                  attrs: { role: 'img' },
                  props: { name: notif.icon }
                })
              );
            }
            else if (notif.avatar) {
              mainChild.push(
                h(QAvatar, { staticClass: 'q-notification__avatar col-auto' }, [
                  h('img', { attrs: { src: notif.avatar, 'aria-hidden': 'true' } })
                ])
              );
            }
          }

          mainChild.push(
            h('div', msgData, msgChild)
          );

          var child = [
            h('div', { staticClass: meta.contentClass }, mainChild)
          ];

          notif.progress === true && child.push(
            h('div', {
              key: ((meta.uid) + "|p|" + (meta.badge)),
              staticClass: 'q-notification__progress',
              style: meta.progressStyle,
              class: notif.progressClass
            })
          );

          notif.actions !== void 0 && child.push(
            h('div', {
              staticClass: meta.actionsClass
            }, notif.actions.map(function (a) { return h(QBtn, { props: a.props, on: a.on }); }))
          );

          meta.badge > 1 && child.push(
            h('div', {
              key: ((meta.uid) + "|" + (meta.badge)),
              staticClass: meta.badgeStaticClass,
              style: notif.badgeStyle,
              class: notif.badgeClass
            }, [ meta.badge ])
          );

          return h('div', {
            ref: ("notif_" + (meta.uid)),
            key: meta.uid,
            staticClass: meta.staticClass,
            attrs: attrs$2
          }, [
            h('div', { staticClass: meta.wrapperClass }, child)
          ])
        }))
      }))
    }
  };

  var Notify = {
    create: function create (opts) {
      if (isSSR === true) { return noop }
      return this.__vm.add(opts)
    },
    setDefaults: function setDefaults (opts) {
      opts === Object(opts) && Object.assign(defaults$1, opts);
    },
    registerType: function registerType (typeName, typeOpts) {
      if (isSSR !== true && typeOpts === Object(typeOpts)) {
        notifTypes[typeName] = typeOpts;
      }
    },

    install: function install (ref) {
      var cfg = ref.cfg;
      var $q = ref.$q;

      if (isSSR === true) {
        $q.notify = noop;
        $q.notify.setDefaults = noop;
        return
      }

      this.setDefaults(cfg.notify);

      $q.notify = this.create.bind(this);
      $q.notify.setDefaults = this.setDefaults;
      $q.notify.registerType = this.registerType;

      var node = document.createElement('div');
      document.body.appendChild(node);

      this.__vm = new Vue(Notifications);
      this.__vm.$mount(node);
    }
  };

  function encode$1 (value) {
    if (Object.prototype.toString.call(value) === '[object Date]') {
      return '__q_date|' + value.toUTCString()
    }
    if (Object.prototype.toString.call(value) === '[object RegExp]') {
      return '__q_expr|' + value.source
    }
    if (typeof value === 'number') {
      return '__q_numb|' + value
    }
    if (typeof value === 'boolean') {
      return '__q_bool|' + (value ? '1' : '0')
    }
    if (typeof value === 'string') {
      return '__q_strn|' + value
    }
    if (typeof value === 'function') {
      return '__q_strn|' + value.toString()
    }
    if (value === Object(value)) {
      return '__q_objt|' + JSON.stringify(value)
    }

    // hmm, we don't know what to do with it,
    // so just return it as is
    return value
  }

  function decode$1 (value) {
    var type, length, source;

    length = value.length;
    if (length < 9) {
      // then it wasn't encoded by us
      return value
    }

    type = value.substr(0, 8);
    source = value.substring(9);

    switch (type) {
      case '__q_date':
        return new Date(source)

      case '__q_expr':
        return new RegExp(source)

      case '__q_numb':
        return Number(source)

      case '__q_bool':
        return Boolean(source === '1')

      case '__q_strn':
        return '' + source

      case '__q_objt':
        return JSON.parse(source)

      default:
        // hmm, we reached here, we don't know the type,
        // then it means it wasn't encoded by us, so just
        // return whatever value it is
        return value
    }
  }

  function getEmptyStorage () {
    return {
      has: noop,
      getLength: noop,
      getItem: noop,
      getIndex: noop,
      getAll: noop,
      set: noop,
      remove: noop,
      clear: noop,
      isEmpty: noop
    }
  }

  function getStorage (type) {
    var
      webStorage = window[type + 'Storage'],
      get = function (key) {
        var item = webStorage.getItem(key);
        return item
          ? decode$1(item)
          : null
      };

    return {
      has: function (key) { return webStorage.getItem(key) !== null; },
      getLength: function () { return webStorage.length; },
      getItem: get,
      getIndex: function (index) {
        return index < webStorage.length
          ? get(webStorage.key(index))
          : null
      },
      getKey: function (index) {
        return index < webStorage.length
          ? webStorage.key(index)
          : null
      },
      getAll: function () {
        var key;
        var result = {}, len = webStorage.length;

        for (var i = 0; i < len; i++) {
          key = webStorage.key(i);
          result[key] = get(key);
        }

        return result
      },
      getAllKeys: function () {
        var result = [], len = webStorage.length;

        for (var i = 0; i < len; i++) {
          result.push(webStorage.key(i));
        }

        return result
      },
      set: function (key, value) { webStorage.setItem(key, encode$1(value)); },
      remove: function (key) { webStorage.removeItem(key); },
      clear: function () { webStorage.clear(); },
      isEmpty: function () { return webStorage.length === 0; }
    }
  }

  var LocalStorage = {
    install: function install (ref) {
      var $q = ref.$q;

      var storage = isSSR === true || client.has.webStorage === false
        ? getEmptyStorage()
        : getStorage('local');

      $q.localStorage = storage;
      Object.assign(this, storage);
    }
  };

  var SessionStorage = {
    install: function install (ref) {
      var $q = ref.$q;

      var storage = isSSR === true || client.has.webStorage === false
        ? getEmptyStorage()
        : getStorage('session');

      $q.sessionStorage = storage;
      Object.assign(this, storage);
    }
  };



  var plugins = /*#__PURE__*/Object.freeze({
    __proto__: null,
    AddressbarColor: AddressbarColor,
    AppFullscreen: AppFullscreen,
    AppVisibility: AppVisibility,
    BottomSheet: BottomSheet$1,
    Cookies: Cookies,
    Dark: Dark,
    Dialog: Dialog,
    LoadingBar: LoadingBar,
    Loading: Loading,
    Meta: Meta,
    Notify: Notify,
    Platform: Platform,
    Screen: Screen,
    LocalStorage: LocalStorage,
    SessionStorage: SessionStorage
  });

  function fallback (text) {
    var area = document.createElement('textarea');
    area.value = text;
    area.contentEditable = true;
    area.style.position = 'fixed'; // avoid scrolling to bottom

    document.body.appendChild(area);
    area.focus();
    area.select();

    var res = document.execCommand('copy');

    area.remove();
    return res
  }

  function copyToClipboard (text) {
    return navigator.clipboard !== void 0
      ? navigator.clipboard.writeText(text)
      : new Promise(function (resolve, reject) {
        var res = fallback(text);
        if (res) {
          resolve(true);
        }
        else {
          reject(res);
        }
      })
  }

  function clean (link) {
    // allow time for iOS
    setTimeout(function () {
      window.URL.revokeObjectURL(link.href);
    }, 10000);
    link.remove();
  }

  function exportFile (fileName, rawData, mimeType) {
    var blob = new Blob([ rawData ], { type: mimeType || 'text/plain' });

    // IE11 has its own stuff...
    if (window.navigator.msSaveOrOpenBlob) {
      return window.navigator.msSaveOrOpenBlob(blob, fileName)
    }

    var link = document.createElement('a');

    link.download = fileName;
    link.href = window.URL.createObjectURL(blob);

    link.classList.add('hidden');
    link.style.position = 'fixed'; // avoid scrolling to bottom
    document.body.appendChild(link);

    try {
      link.click();
      clean(link);
      return true
    }
    catch (err) {
      clean(link);
      return err
    }
  }

  function openUrl (url, reject) {
    var open = window.open;

    if (Platform.is.cordova === true) {
      if (cordova !== void 0 && cordova.InAppBrowser !== void 0 && cordova.InAppBrowser.open !== void 0) {
        open = cordova.InAppBrowser.open;
      }
      else if (navigator !== void 0 && navigator.app !== void 0) {
        return navigator.app.loadUrl(url, {
          openExternal: true
        })
      }
    }
    else if (Vue.prototype.$q.electron !== void 0) {
      return Vue.prototype.$q.electron.shell.openExternal(url)
    }

    var win = open(url, '_blank');

    if (win) {
      win.focus();
      return win
    }
    else {
      reject && reject();
    }
  }



  var utils = /*#__PURE__*/Object.freeze({
    __proto__: null,
    clone: clone$1,
    colors: colors,
    copyToClipboard: copyToClipboard,
    date: date,
    debounce: debounce,
    dom: dom,
    event: event,
    exportFile: exportFile,
    extend: extend,
    format: format,
    frameDebounce: frameDebounce,
    noop: noop,
    openURL: openUrl,
    patterns: patterns,
    scroll: scroll,
    throttle: throttle,
    uid: uid$2
  });

  Vue.use({ install: install }, {
    components: components$1,
    directives: directives,
    plugins: plugins,
    config: window.quasarConfig || {}
  });

  var index_umd = Object.assign({}, {version: version,
    lang: lang,
    iconSet: iconSet,
    components: components$1,
    directives: directives,
    plugins: plugins,
    utils: utils},
    components$1,
    directives,
    plugins,
    utils);

  return index_umd;

})));
