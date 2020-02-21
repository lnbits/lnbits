import { Component, createRef } from 'preact'
import QRCode from 'qrcode'

import { checkSize } from '../lib/fontSize'
import { createInvoice } from '../lib/api'

import { Button } from './button'
import { Modal } from './modal'
import { Loader } from './loader'


const pad = [
	"1",
	"2",
	"3",
	"C",
	"4",
	"5",
	"6",
	"7",
	"8",
	"9",
	"OK",
	"DEL",
	"0",
	"."
];

export default class App extends Component {
	state = {
		init: true,
		payValue: "",
		sanitizedValue: 0,
		fontSize: 150,
		rate: 9713.9,
		satoshis: 0
	}

	display = createRef()

	changeSize = (size = false) => {
		this.setState({
			fontSize: checkSize(
				this.display.current,
				size ? size : this.state.fontSize
			)
		})
	}

	handleCancel = () => {
		if (this.state.payValue === "") return
		this.setState({
			payValue: "",
			sanitizedValue: 0,
			satoshis: 0
		},
			this.changeSize(150)
		)
	}

	resetInvoice = async () => {
		this.setState({
			invoice: null,
			invoiceQR: null,
		}, this.handleCancel)
	}

	handleInvoice = async () => {
		if (!this.state.sanitizedValue) {
			return console.debug('Zero amount not allowed!')
		}
		const { satoshis } = this.state
		const invoice = await createInvoice(satoshis)
		const qr = await this.generateQR(invoice.payment_request)
		this.setState({ invoice, invoiceQR: qr })
	}

	generateQR = async (address) => {
		try {
			return await QRCode.toDataURL(address, { margin: 0 })
		} catch (err) {
			console.error(err)
		}
	}

	handleInput = e => {
		e.preventDefault()
		const key = e.target.innerText
		let value = this.state.payValue
		if (key === 'OK') {
			return this.handleInvoice()
		}
		if (key === "C") {
			return this.handleCancel()
		}
		if (key === "DEL") {
			value = value.substring(0, value.length - 1)
			if (value === "0") {
				value = ""
			}
			const satoshis = this.calcSatoshis(Math.round(parseFloat(value) * 100) / 100)
			return this.setState({
				payValue: value,
				sanitizedValue: Math.round(parseFloat(value) * 100) / 100,
				satoshis
			},
				this.changeSize
			)
		}
		if (key === "." && value.includes(key)) return
		if (value === '' && key === ".")
			return this.setState({
				payValue: "0."
			}, this.changeSize)
		value = this.state.payValue + e.target.innerText
		const satoshis = this.calcSatoshis(Math.round(parseFloat(value) * 100) / 100)
		this.setState({
			payValue: value,
			sanitizedValue: Math.round(parseFloat(value) * 100) / 100,
			satoshis
		},
			this.changeSize
		)
		return
	}

	calcSatoshis = price => {
		const {
			rate
		} = this.state
		if (!price || !rate) return
		let conversion = price / rate
		let sats = Math.round(conversion * 1e8)
		return sats
	}

	updateSettings = async () => {
		this.handleCancel()
		this.setState({
			loading: false,
			config: {
				currency: 'USD',
				lang: 'en'

			}
		})
	}

	componentDidMount = async () => {
		this.updateSettings()
	}

	render({ }, { payValue, fontSize, satoshis, invoice = null, loading = true, config }) {
		return (			
			<div id="app">
				{loading ? <Loader /> : null}
				<div class="display">
					<p style={`font-size: ${fontSize}px`} ref={this.display}>
						{payValue ? <span class="symbol">{config.currency.toUpperCase()}</span> : null}
						{payValue ? payValue : null}
						{satoshis ? <span class="sats">{`${satoshis} sats`}</span> : null}
					</p>
				</div>
				<div class="keypad">
					{pad.map(b => (
						<Button value={b} action={this.handleInput} />
					))}
				</div>
				{invoice && <Modal open={invoice} qr={this.state.invoiceQR} value={this.state.sanitizedValue} sats={satoshis} rate={this.state.rate} symbol={config.currency} close={this.resetInvoice} />}
			</div>
		)
	}
}
