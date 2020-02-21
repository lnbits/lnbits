const getWidth = (element, content = false) => {
    const styles = window.getComputedStyle(element)
    const width = content ? element.scrollWidth : element.clientWidth
    const borderLeft = parseFloat(styles.borderLeftWidth)
    const borderRight = parseFloat(styles.borderRightWidth)
    const padLeft = parseFloat(styles.paddingLeft)
    const padRight = parseFloat(styles.paddingRight)

    return width - borderLeft - borderRight - padLeft - padRight
}

export const checkSize = (el, FONT_SIZE = 150) => {
    let maxWidth = getWidth(el.parentElement)
    let curWidth = getWidth(el, 1)
    let fontSize = FONT_SIZE
    const gamma = maxWidth / curWidth
    // console.debug(maxWidth, curWidth)

    if (curWidth > maxWidth) {
        fontSize = Math.floor(fontSize * gamma)
        // console.debug("down")
        return fontSize
    }

    if (curWidth < maxWidth && fontSize < 150) {
        fontSize = Math.min(fontSize * gamma, 150)
        // console.debug("up")
        return fontSize
    }

    return fontSize
}