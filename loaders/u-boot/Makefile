# user can specify the node and variant but we used M1_Released 
VARIANT ?= released
NODE ?= M1

NODES=M1

help:
	@echo
	@echo "BUILDs 		-- A one shut activity that untars and patches the u-boot for a Node type and variant."
	@echo
	@echo " 	Build a u-boot for the specified node"
	@echo " 	Current nodes are : $(NODES)"
	@echo " 	example: builds the 'released' version of M1 u-boot"
	@echo " 		make M1"
	@echo " 	example: builds Joe's variant of M1 u-boot"
	@echo " 		VARIANT=joe make M1"
	@echo
	@echo "VARIANTs 	-- Custom u-boot version for a specific node."
	@echo
	@echo "     To create your own u-boot variant, create a patch set and config for that variant"
	@echo "     Example : cp patch_0000.M1.released.base patch_0010.M1.kdump.base"
	@echo "          or : ln -s patch_0000.M1.released.base patch_0010.M1.kdump.base"
	@echo "     to build it, execute: VARIANT=joe make M1"
	@echo
	@echo "SAVING     	-- to save your work, you need to regenerate the patch."
	@echo
	@echo "     You'll have to do this by hand using the original tarball against your distclean'ed new source."
	@echo "     Then execute: NODE=M1 make patch"
	@echo "     Or          : NODE=M1 VARIANT=debug make patch"
	@echo "     This will genarte a patch in file M1_released/patch, which you can add as the next sequenced patch"
	@echo "     in patches/patchXXXX_M1_released.patchname. All patches are applied in order of their XXXX value."
	@echo "     Note that if that patch applies to multiple variants, create symb links for it. And test the"
	@echo "     patches for that variant."
	@echo
	@echo "CLEANUP  	-- run 'make cleanall'"
	@echo "     This command will remove all of the u-boot source you are working on!!!"
	@echo "     Make sure you have created your patch first!!!"

M1_config       = da850_am18xxevm
M1_uver         = 2011.12

$(NODES):
	@mkdir -p $@_$(VARIANT)
	@[ "patches/patch.$@.$(VARIANT)" ] || ( echo "Patch files patches/\*.$@.$(VARIANT), not found." && exit 1 )
	@[ -d $@/u-boot-$($(@)_source) ] || \
		( \
			echo -n "Un-tarring u-boot source..." ;\
			mkdir -p $@_$(VARIANT) ;\
			( \
				cd $@_$(VARIANT) && tar xf ../source/u-boot-$($@_uver).tgz  ;\
			) ;\
			echo "Done." ;\
		)
	@./patchuboot $($(@)_uver) $@ $(VARIANT)
	@ echo "To build, goto the $@_$(VARIANT)/u-boot-$($(@)_uver) directory and execute a rmake $($@_config)_config and rmake"

patch:
	@./makepatch "$($(NODE)_uver)" "$(NODE)" "$(VARIANT)"
        

cleanall:
	@for node in $(NODES); do /bin/rm -rf $$node*; done
