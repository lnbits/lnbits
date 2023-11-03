/*! vue-qrcode v2.0.0 | (c) 2018-present Chen Fengyuan | MIT */
(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory(require('vue'), require('qrcode')) :
  typeof define === 'function' && define.amd ? define(['vue', 'qrcode'], factory) :
  (global = typeof globalThis !== 'undefined' ? globalThis : global || self, global.VueQrcode = factory(global.Vue, global.QRCode));
})(this, (function (vue, qrcode) { 'use strict';

  const EVENT_READY = 'ready';
  var index = vue.defineComponent({
      name: 'VueQrcode',
      props: {
          /**
           * The value of the QR code.
           */
          value: {
              type: String,
              default: undefined,
          },
          /**
           * The options for the QR code generator.
           * {@link https://github.com/soldair/node-qrcode#qr-code-options}
           */
          options: {
              type: Object,
              default: undefined,
          },
          /**
           * The tag name of the component's root element.
           */
          tag: {
              type: String,
              default: 'canvas',
          },
      },
      emits: [EVENT_READY],
      watch: {
          $props: {
              deep: true,
              immediate: true,
              /**
               * Update the QR code when props changed.
               */
              handler() {
                  if (this.$el) {
                      this.generate();
                  }
              },
          },
      },
      mounted() {
          this.generate();
      },
      methods: {
          /**
           * Generate QR code.
           */
          generate() {
              const options = this.options || {};
              const value = String(this.value);
              const done = () => {
                  this.$emit(EVENT_READY, this.$el);
              };
              switch (this.tag) {
                  case 'canvas':
                      qrcode.toCanvas(this.$el, value, options, (error) => {
                          if (error) {
                              throw error;
                          }
                          done();
                      });
                      break;
                  case 'img':
                      qrcode.toDataURL(value, options, (error, url) => {
                          if (error) {
                              throw error;
                          }
                          this.$el.src = url;
                          this.$el.onload = done;
                      });
                      break;
                  case 'svg':
                      qrcode.toString(value, options, (error, string) => {
                          if (error) {
                              throw error;
                          }
                          const div = document.createElement('div');
                          div.innerHTML = string;
                          const svg = div.querySelector('svg');
                          if (svg) {
                              const { attributes, childNodes } = svg;
                              Object.keys(attributes).forEach((key) => {
                                  const attribute = attributes[Number(key)];
                                  this.$el.setAttribute(attribute.name, attribute.value);
                              });
                              Object.keys(childNodes).forEach((key) => {
                                  const childNode = childNodes[Number(key)];
                                  this.$el.appendChild(childNode.cloneNode(true));
                              });
                              done();
                          }
                      });
                      break;
              }
          },
      },
      render() {
          return vue.h(this.tag, this.$slots.default);
      },
  });

  return index;

}));
