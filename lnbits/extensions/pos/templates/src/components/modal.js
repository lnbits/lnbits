import { useState, useEffect, useContext } from 'preact/hooks'
import { checkInvoice } from '../lib/api'

export const Modal = ({open, qr, value, sats, symbol, rate, close}) => {

    const [status, setStatus] = useState(false)
    const [check, doCheck] = useState(0)

    const poll = setTimeout(() => doCheck(check + 1), 1000)

    const closeModal = () => {
        clearTimeout(poll)
        return close()
    }
    
    useEffect(async () => {
        const lntx = await checkInvoice(open)
        if(!lntx){
            return poll
        } 
        if(lntx) {
            return setStatus(true)
        }
        return () => (clearTimeout(poll))
    }, [check])

    return (
        <div class={`modal ${open ? 'open' : null} ${status ? 'settled' : null}`} data-modal="payment-modal">
            <article class="content-wrapper">
                <button onClick={closeModal} class="close"></button>
                <header class="modal-header">
                    <h2><small>{symbol.toUpperCase()}</small>{` ${value}`}</h2>
                </header>
                <div class="content">
                    {!status && 
                    <>
                        <p>{`Scan to pay ${sats} sats`}</p>
                        <img src={qr} class="img-responsive" alt={open}/>
                        <p><small>{`1 BTC = ${symbol} ${rate.toFixed(2)}`}</small></p>
                    </>}
                    {status && 
                    <>
                        <svg class="checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52"><circle class="checkmark__circle" cx="26" cy="26" r="25" fill="none"/><path class="checkmark__check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/></svg>
                        <p>{`${sats} sats payed!`}</p>
                    </>}
                </div>
            </article>
        </div>
    )
}