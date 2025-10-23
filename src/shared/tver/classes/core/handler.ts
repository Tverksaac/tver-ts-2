import { get_logger, is_client_context } from "shared/tver/utility/utils"

export abstract class Handler {
    public Type = is_client_context()? "Client" : "Server"
    public Active = false
    public log = get_logger("[" + this.Type.upper() + "]")

    private readonly _registered: ModuleScript[] = []

    constructor () {}

    public Register(ToLoad: Folder | ModuleScript) {
        if (this.Active) {this.log.w("Cant Register after " + this.Type + " Was Active"); return}

        if (ToLoad.IsA("ModuleScript")) {
            this._registered.push(ToLoad)
        } else if (ToLoad.IsA("Folder")) {
            ToLoad.GetDescendants().forEach((instance) => {
                if (instance.IsA("ModuleScript")) {
                    this._registered.push(instance)
                }
            })
        } else {
            this.log.w("Cant Register " + ToLoad)
        }
    }

    public Load() {
        if (this.Active) {this.log.w(this.Type + " cant be loaded after activation!"); return}

        const _failed: defined[] = []

        this._registered.forEach((module) => {
            let _, result = pcall(() => {
                require(module)
            })
            if (!result[0]) {
                this.log.e(module.Name + " Expirienced error while loading!")
            }
        })
    }
}