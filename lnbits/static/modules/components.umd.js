!(function (e) {
  'function' == typeof define && define.amd ? define(e) : e()
})(function () {
  'use strict'
  var e = {}
  const n = 'production' !== e.NODE_ENV ? Object.freeze({}) : {},
    t = 'production' !== e.NODE_ENV ? Object.freeze([]) : [],
    o = () => {},
    r = e =>
      111 === e.charCodeAt(0) &&
      110 === e.charCodeAt(1) &&
      (e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97),
    s = Object.assign,
    c = Array.isArray,
    l = e => 'function' == typeof e,
    i = e => 'string' == typeof e,
    a = e => 'symbol' == typeof e,
    u = e => null !== e && 'object' == typeof e,
    p = Object.prototype.toString,
    d = e => p.call(e),
    f = e => {
      const n = Object.create(null)
      return t => n[t] || (n[t] = e(t))
    },
    h = /-\w/g,
    g = f(e => e.replace(h, e => e.slice(1).toUpperCase())),
    m = f(e => e.charAt(0).toUpperCase() + e.slice(1))
  let y
  const _ = () =>
    y ||
    (y =
      'undefined' != typeof globalThis
        ? globalThis
        : 'undefined' != typeof self
          ? self
          : 'undefined' != typeof window
            ? window
            : 'undefined' != typeof global
              ? global
              : {})
  function v(e) {
    if (c(e)) {
      const n = {}
      for (let t = 0; t < e.length; t++) {
        const o = e[t],
          r = i(o) ? C(o) : v(o)
        if (r) for (const e in r) n[e] = r[e]
      }
      return n
    }
    if (i(e) || u(e)) return e
  }
  const b = /;(?![^(]*\))/g,
    w = /:([^]+)/,
    E = /\/\*[^]*?\*\//g
  function C(e) {
    const n = {}
    return (
      e
        .replace(E, '')
        .split(b)
        .forEach(e => {
          if (e) {
            const t = e.split(w)
            t.length > 1 && (n[t[0].trim()] = t[1].trim())
          }
        }),
      n
    )
  }
  function N(e) {
    let n = ''
    if (i(e)) n = e
    else if (c(e))
      for (let t = 0; t < e.length; t++) {
        const o = N(e[t])
        o && (n += o + ' ')
      }
    else if (u(e)) for (const t in e) e[t] && (n += t + ' ')
    return n.trim()
  }
  const k = e => !(!e || !0 !== e.__v_isRef),
    x = e =>
      i(e)
        ? e
        : null == e
          ? ''
          : c(e) || (u(e) && (e.toString === p || !l(e.toString)))
            ? k(e)
              ? x(e.value)
              : JSON.stringify(e, S, 2)
            : String(e),
    S = (e, n) =>
      k(n)
        ? S(e, n.value)
        : (e => '[object Map]' === d(e))(n)
          ? {
              [`Map(${n.size})`]: [...n.entries()].reduce(
                (e, [n, t], o) => ((e[O(n, o) + ' =>'] = t), e),
                {}
              )
            }
          : (e => '[object Set]' === d(e))(n)
            ? {[`Set(${n.size})`]: [...n.values()].map(e => O(e))}
            : a(n)
              ? O(n)
              : !u(n) || c(n) || (e => '[object Object]' === d(e))(n)
                ? n
                : String(n),
    O = (e, n = '') => {
      var t
      return a(e) ? `Symbol(${null != (t = e.description) ? t : n})` : e
    }
  function V(e) {
    return $(e) ? V(e.__v_raw) : !(!e || !e.__v_isReactive)
  }
  function $(e) {
    return !(!e || !e.__v_isReadonly)
  }
  function j(e) {
    return !(!e || !e.__v_isShallow)
  }
  function F(e) {
    return !!e && !!e.__v_raw
  }
  function R(e) {
    const n = e && e.__v_raw
    return n ? R(n) : e
  }
  function D(e) {
    return !!e && !0 === e.__v_isRef
  }
  new Set(
    Object.getOwnPropertyNames(Symbol)
      .filter(e => 'arguments' !== e && 'caller' !== e)
      .map(e => Symbol[e])
      .filter(a)
  )
  var T = {}
  const A = []
  let I = !1
  function M(e, ...n) {
    if (I) return
    I = !0
    const t = A.length ? A[A.length - 1].component : null,
      o = t && t.appContext.config.warnHandler,
      r = (function () {
        let e = A[A.length - 1]
        if (!e) return []
        const n = []
        for (; e; ) {
          const t = n[0]
          t && t.vnode === e
            ? t.recurseCount++
            : n.push({vnode: e, recurseCount: 0})
          const o = e.component && e.component.parent
          e = o && o.vnode
        }
        return n
      })()
    if (o)
      q(o, t, 11, [
        e +
          n
            .map(e => {
              var n, t
              return null != (t = null == (n = e.toString) ? void 0 : n.call(e))
                ? t
                : JSON.stringify(e)
            })
            .join(''),
        t && t.proxy,
        r.map(({vnode: e}) => `at <${Te(t, e.type)}>`).join('\n'),
        r
      ])
    else {
      const t = [`[Vue warn]: ${e}`, ...n]
      ;(r.length &&
        t.push(
          '\n',
          ...(function (e) {
            const n = []
            return (
              e.forEach((e, t) => {
                n.push(
                  ...(0 === t ? [] : ['\n']),
                  ...(function ({vnode: e, recurseCount: n}) {
                    const t = n > 0 ? `... (${n} recursive calls)` : '',
                      o = !!e.component && null == e.component.parent,
                      r = ` at <${Te(e.component, e.type, o)}`,
                      s = '>' + t
                    return e.props ? [r, ...U(e.props), s] : [r + s]
                  })(e)
                )
              }),
              n
            )
          })(r)
        ),
        console.warn(...t))
    }
    I = !1
  }
  function U(e) {
    const n = [],
      t = Object.keys(e)
    return (
      t.slice(0, 3).forEach(t => {
        n.push(...H(t, e[t]))
      }),
      t.length > 3 && n.push(' ...'),
      n
    )
  }
  function H(e, n, t) {
    return i(n)
      ? ((n = JSON.stringify(n)), t ? n : [`${e}=${n}`])
      : 'number' == typeof n || 'boolean' == typeof n || null == n
        ? t
          ? n
          : [`${e}=${n}`]
        : D(n)
          ? ((n = H(e, R(n.value), !0)), t ? n : [`${e}=Ref<`, n, '>'])
          : l(n)
            ? [`${e}=fn${n.name ? `<${n.name}>` : ''}`]
            : ((n = R(n)), t ? n : [`${e}=`, n])
  }
  const P = {
    sp: 'serverPrefetch hook',
    bc: 'beforeCreate hook',
    c: 'created hook',
    bm: 'beforeMount hook',
    m: 'mounted hook',
    bu: 'beforeUpdate hook',
    u: 'updated',
    bum: 'beforeUnmount hook',
    um: 'unmounted hook',
    a: 'activated hook',
    da: 'deactivated hook',
    ec: 'errorCaptured hook',
    rtc: 'renderTracked hook',
    rtg: 'renderTriggered hook',
    0: 'setup function',
    1: 'render function',
    2: 'watcher getter',
    3: 'watcher callback',
    4: 'watcher cleanup function',
    5: 'native event handler',
    6: 'component event handler',
    7: 'vnode hook',
    8: 'directive hook',
    9: 'transition hook',
    10: 'app errorHandler',
    11: 'app warnHandler',
    12: 'ref function',
    13: 'async component loader',
    14: 'scheduler flush',
    15: 'component update',
    16: 'app unmount cleanup function'
  }
  function q(e, n, t, o) {
    try {
      return o ? e(...o) : e()
    } catch (r) {
      z(r, n, t)
    }
  }
  function z(e, t, o, r = !0) {
    const s = t ? t.vnode : null,
      {errorHandler: c, throwUnhandledErrorInProduction: l} =
        (t && t.appContext.config) || n
    if (t) {
      let n = t.parent
      const r = t.proxy,
        s =
          'production' !== T.NODE_ENV
            ? P[o]
            : `https://vuejs.org/error-reference/#runtime-${o}`
      for (; n; ) {
        const t = n.ec
        if (t)
          for (let n = 0; n < t.length; n++) if (!1 === t[n](e, r, s)) return
        n = n.parent
      }
      if (c) return void q(c, null, 10, [e, r, s])
    }
    !(function (e, n, t, o = !0, r = !1) {
      if ('production' !== T.NODE_ENV) {
        const r = P[n]
        if (
          (t && ((s = t), A.push(s)),
          M('Unhandled error' + (r ? ` during execution of ${r}` : '')),
          t && A.pop(),
          o)
        )
          throw e
        console.error(e)
      } else {
        if (r) throw e
        console.error(e)
      }
      var s
    })(e, o, s, r, l)
  }
  const B = []
  let G = -1
  const J = []
  let W = null,
    L = 0
  const K = Promise.resolve()
  let Q = null
  function X(e) {
    if (!(1 & e.flags)) {
      const n = Z(e),
        t = B[B.length - 1]
      ;(!t || (!(2 & e.flags) && n >= Z(t))
        ? B.push(e)
        : B.splice(
            (function (e) {
              let n = G + 1,
                t = B.length
              for (; n < t; ) {
                const o = (n + t) >>> 1,
                  r = B[o],
                  s = Z(r)
                s < e || (s === e && 2 & r.flags) ? (n = o + 1) : (t = o)
              }
              return n
            })(n),
            0,
            e
          ),
        (e.flags |= 1),
        Y())
    }
  }
  function Y() {
    Q || (Q = K.then(ee))
  }
  const Z = e => (null == e.id ? (2 & e.flags ? -1 : 1 / 0) : e.id)
  function ee(e) {
    'production' !== T.NODE_ENV && (e = e || new Map())
    const n = 'production' !== T.NODE_ENV ? n => ne(e, n) : o
    try {
      for (G = 0; G < B.length; G++) {
        const e = B[G]
        if (e && !(8 & e.flags)) {
          if ('production' !== T.NODE_ENV && n(e)) continue
          ;(4 & e.flags && (e.flags &= -2),
            q(e, e.i, e.i ? 15 : 14),
            4 & e.flags || (e.flags &= -2))
        }
      }
    } finally {
      for (; G < B.length; G++) {
        const e = B[G]
        e && (e.flags &= -2)
      }
      ;((G = -1),
        (B.length = 0),
        (function (e) {
          if (J.length) {
            const n = [...new Set(J)].sort((e, n) => Z(e) - Z(n))
            if (((J.length = 0), W)) return void W.push(...n)
            for (
              W = n, 'production' !== T.NODE_ENV && (e = e || new Map()), L = 0;
              L < W.length;
              L++
            ) {
              const n = W[L]
              ;('production' !== T.NODE_ENV && ne(e, n)) ||
                (4 & n.flags && (n.flags &= -2),
                8 & n.flags || n(),
                (n.flags &= -2))
            }
            ;((W = null), (L = 0))
          }
        })(e),
        (Q = null),
        (B.length || J.length) && ee(e))
    }
  }
  function ne(e, n) {
    const t = e.get(n) || 0
    if (t > 100) {
      const e = n.i,
        t = e && De(e.type)
      return (
        z(
          `Maximum recursive updates exceeded${t ? ` in component <${t}>` : ''}. This means you have a reactive effect that is mutating its own dependencies and thus recursively triggering itself. Possible sources include component template, render function, updated hook or watcher source function.`,
          null,
          10
        ),
        !0
      )
    }
    return (e.set(n, t + 1), !1)
  }
  const te = new Map()
  'production' !== T.NODE_ENV &&
    (_().__VUE_HMR_RUNTIME__ = {
      createRecord: ce(function (e, n) {
        if (oe.has(e)) return !1
        return (oe.set(e, {initialDef: re(n), instances: new Set()}), !0)
      }),
      rerender: ce(function (e, n) {
        const t = oe.get(e)
        if (!t) return
        ;((t.initialDef.render = n),
          [...t.instances].forEach(e => {
            ;(n && ((e.render = n), (re(e.type).render = n)),
              (e.renderCache = []),
              8 & e.job.flags || e.update())
          }))
      }),
      reload: ce(function (e, n) {
        const t = oe.get(e)
        if (!t) return
        ;((n = re(n)), se(t.initialDef, n))
        const o = [...t.instances]
        for (let s = 0; s < o.length; s++) {
          const e = o[s],
            r = re(e.type)
          let c = te.get(r)
          ;(c || (r !== t.initialDef && se(r, n), te.set(r, (c = new Set()))),
            c.add(e),
            e.appContext.propsCache.delete(e.type),
            e.appContext.emitsCache.delete(e.type),
            e.appContext.optionsCache.delete(e.type),
            e.ceReload
              ? (c.add(e), e.ceReload(n.styles), c.delete(e))
              : e.parent
                ? X(() => {
                    8 & e.job.flags || (e.parent.update(), c.delete(e))
                  })
                : e.appContext.reload
                  ? e.appContext.reload()
                  : 'undefined' != typeof window
                    ? window.location.reload()
                    : console.warn(
                        '[HMR] Root or manually mounted instance modified. Full reload required.'
                      ),
            e.root.ce && e !== e.root && e.root.ce._removeChildStyle(r))
        }
        ;((r = () => {
          te.clear()
        }),
          c(r)
            ? J.push(...r)
            : W && -1 === r.id
              ? W.splice(L + 1, 0, r)
              : 1 & r.flags || (J.push(r), (r.flags |= 1)),
          Y())
        var r
      })
    })
  const oe = new Map()
  function re(e) {
    return Ae(e) ? e.__vccOpts : e
  }
  function se(e, n) {
    s(e, n)
    for (const t in e) '__file' === t || t in n || delete e[t]
  }
  function ce(e) {
    return (n, t) => {
      try {
        return e(n, t)
      } catch (o) {
        ;(console.error(o),
          console.warn(
            '[HMR] Something went wrong during Vue component hot-reload. Full reload required.'
          ))
      }
    }
  }
  let le = null
  function ie(e, n) {
    6 & e.shapeFlag && e.component
      ? ((e.transition = n), ie(e.component.subTree, n))
      : 128 & e.shapeFlag
        ? ((e.ssContent.transition = n.clone(e.ssContent)),
          (e.ssFallback.transition = n.clone(e.ssFallback)))
        : (e.transition = n)
  }
  ;(_().requestIdleCallback, _().cancelIdleCallback)
  function ae(e, n) {
    return (
      (function (e, n, t = !0, o = !1) {
        const r = je
        if (r) {
          const s = r.type
          {
            const e = De(s, !1)
            if (e && (e === n || e === g(n) || e === m(g(n)))) return s
          }
          const c = pe(r[e] || s[e], n) || pe(r.appContext[e], n)
          if (!c && o) return s
          if ('production' !== T.NODE_ENV && t && !c) {
            const t =
              '\nIf this is a native custom element, make sure to exclude it from component resolution via compilerOptions.isCustomElement.'
            M(`Failed to resolve ${e.slice(0, -1)}: ${n}${t}`)
          }
          return c
        }
        'production' !== T.NODE_ENV &&
          M(
            `resolve${m(e.slice(0, -1))} can only be used in render() or setup().`
          )
      })('components', e, !0, n) || e
    )
  }
  const ue = Symbol.for('v-ndc')
  function pe(e, n) {
    return e && (e[n] || e[g(n)] || e[m(g(n))])
  }
  const de = {},
    fe = e => Object.getPrototypeOf(e) === de,
    he = Symbol.for('v-fgt'),
    ge = Symbol.for('v-txt'),
    me = Symbol.for('v-cmt'),
    ye = []
  let _e = null
  function ve(e = !1) {
    ye.push((_e = e ? null : []))
  }
  function be(e) {
    return (
      (e.dynamicChildren = _e || t),
      ye.pop(),
      (_e = ye[ye.length - 1] || null),
      _e && _e.push(e),
      e
    )
  }
  function we(e, n, t, o, r) {
    return be(ke(e, n, t, o, r, !0))
  }
  const Ee = ({key: e}) => (null != e ? e : null),
    Ce = ({ref: e, ref_key: n, ref_for: t}) => (
      'number' == typeof e && (e = '' + e),
      null != e
        ? i(e) || D(e) || l(e)
          ? {i: le, r: e, k: n, f: !!t}
          : e
        : null
    )
  function Ne(
    e,
    n = null,
    t = null,
    o = 0,
    r = null,
    s = e === he ? 0 : 1,
    c = !1,
    l = !1
  ) {
    const a = {
      __v_isVNode: !0,
      __v_skip: !0,
      type: e,
      props: n,
      key: n && Ee(n),
      ref: n && Ce(n),
      scopeId: null,
      slotScopeIds: null,
      children: t,
      component: null,
      suspense: null,
      ssContent: null,
      ssFallback: null,
      dirs: null,
      transition: null,
      el: null,
      anchor: null,
      target: null,
      targetStart: null,
      targetAnchor: null,
      staticCount: 0,
      shapeFlag: s,
      patchFlag: o,
      dynamicProps: r,
      dynamicChildren: null,
      appContext: null,
      ctx: le
    }
    return (
      l
        ? ($e(a, t), 128 & s && e.normalize(a))
        : t && (a.shapeFlag |= i(t) ? 8 : 16),
      'production' !== T.NODE_ENV &&
        a.key != a.key &&
        M('VNode created with invalid key (NaN). VNode type:', a.type),
      !c &&
        _e &&
        (a.patchFlag > 0 || 6 & s) &&
        32 !== a.patchFlag &&
        _e.push(a),
      a
    )
  }
  const ke = 'production' !== T.NODE_ENV ? (...e) => xe(...e) : xe
  function xe(e, n = null, t = null, o = 0, r = null, a = !1) {
    if (
      ((e && e !== ue) ||
        ('production' === T.NODE_ENV ||
          e ||
          M(`Invalid vnode type when creating vnode: ${e}.`),
        (e = me)),
      (p = e) && !0 === p.__v_isVNode)
    ) {
      const o = Se(e, n, !0)
      return (
        t && $e(o, t),
        !a && _e && (6 & o.shapeFlag ? (_e[_e.indexOf(e)] = o) : _e.push(o)),
        (o.patchFlag = -2),
        o
      )
    }
    var p
    if ((Ae(e) && (e = e.__vccOpts), n)) {
      n = (function (e) {
        return e ? (F(e) || fe(e) ? s({}, e) : e) : null
      })(n)
      let {class: e, style: t} = n
      ;(e && !i(e) && (n.class = N(e)),
        u(t) && (F(t) && !c(t) && (t = s({}, t)), (n.style = v(t))))
    }
    const d = i(e)
      ? 1
      : (e => e.__isSuspense)(e)
        ? 128
        : (e => e.__isTeleport)(e)
          ? 64
          : u(e)
            ? 4
            : l(e)
              ? 2
              : 0
    return (
      'production' !== T.NODE_ENV &&
        4 & d &&
        F(e) &&
        M(
          'Vue received a Component that was made a reactive object. This can lead to unnecessary performance overhead and should be avoided by marking the component with `markRaw` or using `shallowRef` instead of `ref`.',
          '\nComponent that was made reactive: ',
          (e = R(e))
        ),
      Ne(e, n, t, o, r, d, a, !0)
    )
  }
  function Se(e, n, t = !1, o = !1) {
    const {props: s, ref: l, patchFlag: i, children: a, transition: u} = e,
      p = n
        ? (function (...e) {
            const n = {}
            for (let t = 0; t < e.length; t++) {
              const o = e[t]
              for (const e in o)
                if ('class' === e)
                  n.class !== o.class && (n.class = N([n.class, o.class]))
                else if ('style' === e) n.style = v([n.style, o.style])
                else if (r(e)) {
                  const t = n[e],
                    r = o[e]
                  !r ||
                    t === r ||
                    (c(t) && t.includes(r)) ||
                    (n[e] = t ? [].concat(t, r) : r)
                } else '' !== e && (n[e] = o[e])
            }
            return n
          })(s || {}, n)
        : s,
      d = {
        __v_isVNode: !0,
        __v_skip: !0,
        type: e.type,
        props: p,
        key: p && Ee(p),
        ref:
          n && n.ref
            ? t && l
              ? c(l)
                ? l.concat(Ce(n))
                : [l, Ce(n)]
              : Ce(n)
            : l,
        scopeId: e.scopeId,
        slotScopeIds: e.slotScopeIds,
        children:
          'production' !== T.NODE_ENV && -1 === i && c(a) ? a.map(Oe) : a,
        target: e.target,
        targetStart: e.targetStart,
        targetAnchor: e.targetAnchor,
        staticCount: e.staticCount,
        shapeFlag: e.shapeFlag,
        patchFlag: n && e.type !== he ? (-1 === i ? 16 : 16 | i) : i,
        dynamicProps: e.dynamicProps,
        dynamicChildren: e.dynamicChildren,
        appContext: e.appContext,
        dirs: e.dirs,
        transition: u,
        component: e.component,
        suspense: e.suspense,
        ssContent: e.ssContent && Se(e.ssContent),
        ssFallback: e.ssFallback && Se(e.ssFallback),
        placeholder: e.placeholder,
        el: e.el,
        anchor: e.anchor,
        ctx: e.ctx,
        ce: e.ce
      }
    return (u && o && ie(d, u.clone(d)), d)
  }
  function Oe(e) {
    const n = Se(e)
    return (c(e.children) && (n.children = e.children.map(Oe)), n)
  }
  function Ve(e = ' ', n = 0) {
    return ke(ge, null, e, n)
  }
  function $e(e, n) {
    let t = 0
    const {shapeFlag: o} = e
    if (null == n) n = null
    else if (c(n)) t = 16
    else if ('object' == typeof n) {
      if (65 & o) {
        const t = n.default
        return void (
          t && (t._c && (t._d = !1), $e(e, t()), t._c && (t._d = !0))
        )
      }
      t = 32
      n._ || fe(n) || (n._ctx = le)
    } else
      l(n)
        ? ((n = {default: n, _ctx: le}), (t = 32))
        : ((n = String(n)), 64 & o ? ((t = 16), (n = [Ve(n)])) : (t = 8))
    ;((e.children = n), (e.shapeFlag |= t))
  }
  let je = null
  {
    const e = _(),
      n = (n, t) => {
        let o
        return (
          (o = e[n]) || (o = e[n] = []),
          o.push(t),
          e => {
            o.length > 1 ? o.forEach(n => n(e)) : o[0](e)
          }
        )
      }
    ;(n('__VUE_INSTANCE_SETTERS__', e => (je = e)),
      n('__VUE_SSR_SETTERS__', e => e))
  }
  const Fe = /(?:^|[-_])\w/g,
    Re = e => e.replace(Fe, e => e.toUpperCase()).replace(/[-_]/g, '')
  function De(e, n = !0) {
    return l(e) ? e.displayName || e.name : e.name || (n && e.__name)
  }
  function Te(e, n, t = !1) {
    let o = De(n)
    if (!o && n.__file) {
      const e = n.__file.match(/([^/\\]+)\.\w+$/)
      e && (o = e[1])
    }
    if (!o && e) {
      const t = e => {
        for (const t in e) if (e[t] === n) return t
      }
      o =
        t(e.components) ||
        (e.parent && t(e.parent.type.components)) ||
        t(e.appContext.components)
    }
    return o ? Re(o) : t ? 'App' : 'Anonymous'
  }
  function Ae(e) {
    return l(e) && '__vccOpts' in e
  }
  function Ie() {
    if ('production' === T.NODE_ENV || 'undefined' == typeof window) return
    const e = {style: 'color:#3ba776'},
      t = {style: 'color:#1677ff'},
      o = {style: 'color:#f5222d'},
      r = {style: 'color:#eb2f96'},
      i = {
        __vue_custom_formatter: !0,
        header(n) {
          if (!u(n)) return null
          if (n.__isVue) return ['div', e, 'VueInstance']
          if (D(n)) {
            const t = n.value
            return ['div', {}, ['span', e, g(n)], '<', d(t), '>']
          }
          return V(n)
            ? [
                'div',
                {},
                ['span', e, j(n) ? 'ShallowReactive' : 'Reactive'],
                '<',
                d(n),
                '>' + ($(n) ? ' (readonly)' : '')
              ]
            : $(n)
              ? [
                  'div',
                  {},
                  ['span', e, j(n) ? 'ShallowReadonly' : 'Readonly'],
                  '<',
                  d(n),
                  '>'
                ]
              : null
        },
        hasBody: e => e && e.__isVue,
        body(e) {
          if (e && e.__isVue) return ['div', {}, ...a(e.$)]
        }
      }
    function a(e) {
      const t = []
      ;(e.type.props && e.props && t.push(p('props', R(e.props))),
        e.setupState !== n && t.push(p('setup', e.setupState)),
        e.data !== n && t.push(p('data', R(e.data))))
      const o = f(e, 'computed')
      o && t.push(p('computed', o))
      const s = f(e, 'inject')
      return (
        s && t.push(p('injected', s)),
        t.push([
          'div',
          {},
          ['span', {style: r.style + ';opacity:0.66'}, '$ (internal): '],
          ['object', {object: e}]
        ]),
        t
      )
    }
    function p(e, n) {
      return (
        (n = s({}, n)),
        Object.keys(n).length
          ? [
              'div',
              {style: 'line-height:1.25em;margin-bottom:0.6em'},
              ['div', {style: 'color:#476582'}, e],
              [
                'div',
                {style: 'padding-left:1.25em'},
                ...Object.keys(n).map(e => [
                  'div',
                  {},
                  ['span', r, e + ': '],
                  d(n[e], !1)
                ])
              ]
            ]
          : ['span', {}]
      )
    }
    function d(e, n = !0) {
      return 'number' == typeof e
        ? ['span', t, e]
        : 'string' == typeof e
          ? ['span', o, JSON.stringify(e)]
          : 'boolean' == typeof e
            ? ['span', r, e]
            : u(e)
              ? ['object', {object: n ? R(e) : e}]
              : ['span', o, String(e)]
    }
    function f(e, n) {
      const t = e.type
      if (l(t)) return
      const o = {}
      for (const r in e.ctx) h(t, r, n) && (o[r] = e.ctx[r])
      return o
    }
    function h(e, n, t) {
      const o = e[t]
      return (
        !!((c(o) && o.includes(n)) || (u(o) && n in o)) ||
        !(!e.extends || !h(e.extends, n, t)) ||
        !(!e.mixins || !e.mixins.some(e => h(e, n, t))) ||
        void 0
      )
    }
    function g(e) {
      return j(e) ? 'ShallowRef' : e.effect ? 'ComputedRef' : 'Ref'
    }
    window.devtoolsFormatters
      ? window.devtoolsFormatters.push(i)
      : (window.devtoolsFormatters = [i])
  }
  'production' !== {}.NODE_ENV && Ie()
  const Me = {class: 'text-center q-pa-md flex flex-center'},
    Ue = ['textContent'],
    He = ['textContent'],
    Pe = {
      class: 'q-mx-auto q-mt-lg justify-center',
      style: {width: 'max-content'}
    }
  const qe = ((e, n) => {
    const t = e.__vccOpts || e
    for (const [o, r] of n) t[o] = r
    return t
  })(
    {
      props: ['dynamic', 'code', 'message'],
      computed: {
        isExtension() {
          return (
            403 == this.code &&
            (!!this.message.startsWith('Extension ') || void 0)
          )
        }
      },
      methods: {
        goBack() {
          window.history.back()
        },
        goHome() {
          window.location = '/'
        },
        goToWallet() {
          this.dynamic
            ? this.$router.push('/wallet')
            : (window.location = '/wallet')
        },
        goToExtension() {
          const e = `/extensions#${this.message.match(/'([^']+)'/)[1]}`
          this.dynamic ? this.$router.push(e) : (window.location = e)
        },
        async logOut() {
          try {
            ;(await LNbits.api.logout(), (window.location = '/'))
          } catch (e) {
            LNbits.utils.notifyApiError(e)
          }
        }
      },
      async created() {
        if (!this.dynamic && 401 == this.code)
          return (
            console.warn(`Unauthorized: ${this.errorMessage}`),
            void this.logOut()
          )
      }
    },
    [
      [
        'render',
        function (e, n, t, o, r, s) {
          const c = ae('q-btn')
          return (
            ve(),
            (l = 'div'),
            (i = Me),
            (a = [
              Ne('div', null, [
                Ne(
                  'div',
                  {class: 'error-code', textContent: x(t.code)},
                  null,
                  8,
                  Ue
                ),
                Ne(
                  'div',
                  {class: 'error-message', textContent: x(t.message)},
                  null,
                  8,
                  He
                ),
                Ne('div', Pe, [
                  s.isExtension
                    ? (ve(),
                      we(c, {
                        key: 0,
                        color: 'primary',
                        onClick: n[0] || (n[0] = e => s.goToExtension()),
                        label: 'Go To Extension'
                      }))
                    : e.g.isUserAuthorized
                      ? (ve(),
                        we(c, {
                          key: 1,
                          color: 'primary',
                          onClick: n[1] || (n[1] = e => s.goToWallet()),
                          label: 'Go to Wallet'
                        }))
                      : (ve(),
                        we(c, {
                          key: 2,
                          color: 'primary',
                          onClick: n[2] || (n[2] = e => s.goBack()),
                          label: 'Go Back'
                        })),
                  n[4] || (n[4] = Ne('span', {class: 'q-mx-md'}, 'OR', -1)),
                  ke(c, {
                    color: 'secondary',
                    onClick: n[3] || (n[3] = e => s.goHome()),
                    label: 'Go Home'
                  })
                ])
              ])
            ]),
            be(Ne(l, i, a, u, p, d, !0))
          )
          var l, i, a, u, p, d
        }
      ]
    ]
  )
  window.LnbitsError = qe
})
