export function map_to_array<K extends defined, V extends defined>(map: Map<K, V>): V[] {
    const array : V[] = []

    map.forEach((value) => {
        array.push(value)
    })

    return array
}