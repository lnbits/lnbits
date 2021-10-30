// TODO(nochiel) Handle errors from LNBits.api calls. 
// - Which errors should the host user see?
// TODO(nochiel) Ref. Use UserManager extension.
// - How do I use/enable another extension as a dependency?
// - Ref. Quasar documentation. Can one blueprint depend on another? What is even a blueprint?
// - FINDOUT: How are Jitsi extensions enabled?
//      - If UserManager isn't in the list of active extensions, ask the user to enable it when he enables Jitsi.
// FIXME(nochiel) We need this.g.user
// TODO(nochiel) Wrap jitsi in  a vue component
/*
 * TODO(nochiel) For each participant, add a 'pay Lightning' component.
 *   - Generates an invoice without an amount.
 *   - Show a QR code.
 *   - Allow the user to copy the bolt11 string.
*/

// When a participant joins a conference, the participant is not running LNBits.
// Therefore, we have 2 options for implementation:
// 1. Custom UX (we'll do this eventually)
//      - Use LibJitsiMeet to create an LNBits extension that only uses jitsi in the backend.
//      - With a custom UX, we can ensure that participants always see our LNBits-Jitsi app and the features we want.
//      - Maximum flexibility.
// 2. Chat commands (simple, easy to prototype)
//      - Use lntxbot/LightningTipBot command UX.
//      - All we have to do is handle commands.
//      - /pay participant_id [amount]
//              - participant is given a blank/filled invoice that they can pay to using an external wallet.
//      - /wallet pay participant_id amount
//              - participant pays participant_id using the balance in their LNBits wallet.
//


// ref. https://github.com/jitsi/jitsi-meet/blob/master/modules/API/external/external_api.js
// import "./external_api.js";
// import "lib-jitsi-meet.min.js";
// import "./jitsi_external_api.js";

const assert = console.assert;

function log(message, ...rest) {
    console.log(`%c ${message}`,  'background: steelblue; color: white; font-size:14px', ...rest);
}


function jitsiFunctions(api) {

    return {


        onConnectionEstablished: function(data) {

            const options = {
                roomName: roomName,
                parentNode: document.querySelector('#meet'),    // TODO(nochiel) Create this node in index.html.
                // height: '700px',         // FIXME(nochiel) Make this 75% of the viewport.
                // onload : jitsiOnload,       // FIXME(nochiel) Goes nowhere des nothing.
                // configOverwrite : {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/config.js
                // interfaceConfigOverwrite: {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/interface_config.js
            }

        },

        hello: function(name) {
            log(`hello ${name}`);
        },

    }
}

const app = new Vue({
    el: '#vue',
    mixins: [windowMixin],

    data: function() {
        return { api: null, conference: '',
            participants: [],   // participant: {id, wallet}
        }; },

    /*
    computed: {

        api() {

            let domain = 'meet.jit.si';
            let tenant = 'AAAA';
            let roomName = 'room_AAAA';

            const options = {
                roomName: roomName,
                parentNode: document.querySelector('#meet'),    // TODO(nochiel) Create this node in index.html.
    // height: '500px',         // FIXME(nochiel) Make this 75% of the viewport.
    // onload : jitsiOnload,       // FIXME(nochiel) Goes nowhere des nothing.
    // configOverwrite : {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/config.js
    // interfaceConfigOverwrite: {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/interface_config.js
            };

            let api = new JitsiMeetExternalAPI(domain, options);
            return api;  
        },

    },
    */

    mounted: function () {

        let domain = 'meet.jit.si';
        let tenant = 'AAAA';
        let roomName = 'room_AAAA';

        const options = {
            roomName: roomName,
            parentNode: document.querySelector('#meet'),    // TODO(nochiel) Create this node in index.html.
            height: '700px',         // FIXME(nochiel) Make this 75% of the viewport.
            // onload : jitsiOnload,       // FIXME(nochiel) Goes nowhere des nothing.
            // configOverwrite : {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/config.js
            // interfaceConfigOverwrite: {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/interface_config.js
        };

        this.api = new JitsiMeetExternalAPI(domain, options);
        assert(this.api != null);
        log('this: ', this);
        jitsiFunctions = jitsiFunctions.bind(this);
        jitsiFunctions  = jitsiFunctions(this.api);
        const api = this.api;
        // console.log('jitsi event names:', api.events);

        // FIXME(nochiel) Does nothing. My assumption is that the api is destroyed even though I made it global.
        // FINDOUT How do I do handle events in Vue? Specifically, how do I determine why this listeners aren't running?
        api.on('videoConferenceJoined', this.videoConferenceJoined);
        api.on('participantJoined', this.newParticipant);
        api.on('errorOccurred', function (data) { console.error('error in Jitsi'); });
        api.on('log', function (data) { log('logging'); });


    },

    methods: {

        async test() {
            // TODO(nochiel) Tests for all api flows.
            //
        },

        async videoConferenceJoined(event) {

            {
                participants = this.api.getParticipantsInfo();
                log('videoConferenceJoined: participants:', participants);
            }

            /*
                {
                    roomName: string, // the room name of the conference
                    id: string, // the id of the local participant
                    displayName: string, // the display name of the local participant
                    avatarURL: string // the avatar URL of the local participant
                }
            */

            // This is called when the host/user starts the video conference.

            assert(event.roomName != null);
            this.conference = event.roomName;
            data = {
                conference: event.roomName,     
                admin: event.id,
            };
            LNbits.api
                .request(
                    'POST',
                    '/jitsi/api/v1/conferences',
                    this.g.user.wallets[0].inkey,
                    data
                )
                .then( response => {
                    log('videoConferenceJoined: response from creating conference: ', response.data);
                });

        },


        async getConference(adminId) {

            assert(adminId != null);
            let result = null;
            response = await LNbits.api
                .request(
                    'GET',
                    `/jitsi/api/v1/conference/${adminId}`,
                    this.g.user.wallets[0].inkey,
                )

            if(response != null) {
                result = response.data;
            }

            return result;

        },

        async getParticipant(data) {
            assert(data.participant != '', 'participant id must be given');

            let result = await LNbits.api
                .request(
                    'GET',
                    `/jitsi/api/v1/conference/${data.conference}/participant/${data.participant}`,
                    this.g.user.wallets[0].inkey,
                );
            return result.data;
        },


        async newParticipant(event) {

            /*
                {
                    id: string, // the id of the participant
                    displayName: string // the display name of the participant
                }
                */
            assert(event.id != '');
            log('newParticipant: ', event.id);

            // Give new participants an LNBits account.
            // FINDOUT Should I create a new admin wallet for each conference and save the conference with the wallet?
            if(this.conference != '') {
                log(`newParticipant: creating ${event.id} in conference ${this.conference}`);

                // TODO(nochiel) FINDOUT How do I create a new LNBits wallet? 
                // The LNBits api changes the window location when a new wallet is created. 
                var data = { participant: event.id, conference: this.conference };

                let participant = await this.getParticipant(data);
                log('newParticipant: got participant: ', participant);
                if(participant == null) {

                    // FINDOUT(nochiel) What do we need to store with the participant so that we can generate invoices?
                    // - create a new LNBits userId.
                    // - let walletName = participant.id
                    // FINDOUT(nochiel) How is a user wallet identified?

                    LNbits.api
                        .request(
                            'POST',
                            '/jitsi/api/v1/conference/participant',
                            this.g.user.wallets[0].inkey,
                            data
                        ).then(response => {
                            log('newParticipant: result: ', response.data);
                        });

                }

            }



        },

}

});

