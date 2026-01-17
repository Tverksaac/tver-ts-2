--!strict
--[=[
	A 'Symbol' is an opaque marker type.

	Symbols have the type 'userdata', but when printed to the console, the name
	of the symbol is shown.
	@class Symbol
]=]

local Symbol = {
	id = 0
}

export type Symbol = typeof(newproxy(true))

--[=[
	Creates a Symbol with the given name.

	When printed or coerced to a string, the symbol will turn into the string
	given as its name.

	@param name string
	@return Symbol
]=]
function Symbol.named(name: string): Symbol
	name = name or ''

	local self = newproxy(true)

	local wrappedName = string.format("Symbol(%s)", name).."_"..tostring(Symbol.id)
	Symbol.id += 1

	getmetatable(self).__tostring = function()
		return wrappedName
	end

	print(self)

	return self
end

--[=[
	Returns true if a symbol

	@param value boolean
	@return boolean
]=]
function Symbol.isSymbol(value: any): boolean
	return typeof(value) == "userdata"
end

return {
	CreateSymbol = Symbol.named
}
